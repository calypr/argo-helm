package main

import (
	"bytes"
	"context"
	"crypto/rsa"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"net/http/httputil"
	"net/url"
	"os"
	"strconv"
	"strings"
	"time"

	"github.com/golang-jwt/jwt/v5"
	"github.com/google/go-github/v60/github"
)

type StatusRequest struct {
	RepoURL     string `json:"repo_url"`
	SHA         string `json:"sha"`
	State       string `json:"state"`
	Context     string `json:"context"`
	TargetURL   string `json:"target_url"`
	Description string `json:"description"`
}

// WorkflowEvent describes the JSON payload sent by Argo Workflows notifications.
// It matches the ClusterWorkflowTemplate defined in ADR 0003.
type WorkflowEvent struct {
	Kind        string            `json:"kind"`        // "workflow"
	Event       string            `json:"event"`       // "workflow-pending" | "workflow-succeeded" | "workflow-failed"
	Workflow    string            `json:"workflowName"`
	Namespace   string            `json:"namespace"`
	RepoURL     string            `json:"repoURL"`
	InstallationId string         `json:"installationId, omitempty"` // Optional GitHub App installation ID
	CommitSha   string            `json:"commitSha"`
	Phase       string            `json:"phase,omitempty"` // calculated if missing from labels/status
	StartedAt   string            `json:"startedAt,omitempty"`
	FinishedAt  string            `json:"finishedAt,omitempty"`
	Labels      map[string]string `json:"labels"`
	Annotations map[string]string `json:"annotations"`
	TargetURL   string            `json:"target_url,omitempty"` // URL to the workflow in Argo Workflows UI (optional, composed in template)
	// Status is intentionally left as raw JSON so we don't need a full struct.
	Status any `json:"status"`
}

type StatusResponse struct {
	Success bool   `json:"success"`
	Message string `json:"message"`
}

var (
	githubAppID         int64
	githubAppPrivateKey *rsa.PrivateKey
	httpClient          *http.Client
	debugLogging        bool
)

func main() {
	// Load configuration
	if err := loadConfig(); err != nil {
		log.Fatalf("Failed to load configuration: %v", err)
	}

	// Setup HTTP server
	http.HandleFunc("/status", handleStatus)
	http.HandleFunc("/workflow", handleWorkflow)
	http.HandleFunc("/healthz", handleHealthz)

	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}

	logLevel := os.Getenv("LOG_LEVEL")
	if strings.ToUpper(logLevel) == "DEBUG" {
		debugLogging = true
		log.Printf("DEBUG logging enabled")
	}

	log.Printf("GitHub Status Proxy starting on port %s", port)
	if err := http.ListenAndServe(":"+port, nil); err != nil {
		log.Fatalf("Server failed: %v", err)
	}
}

func loadConfig() error {
	// Load GitHub App ID
	appIDStr := os.Getenv("GITHUB_APP_ID")
	if appIDStr == "" {
		return fmt.Errorf("GITHUB_APP_ID environment variable is required")
	}
	var err error
	githubAppID, err = strconv.ParseInt(appIDStr, 10, 64)
	if err != nil {
		return fmt.Errorf("invalid GITHUB_APP_ID: %w", err)
	}

	// Load GitHub App Private Key
	privateKeyPath := os.Getenv("GITHUB_APP_PRIVATE_KEY_PATH")
	if privateKeyPath == "" {
		privateKeyPath = "/etc/github/private-key.pem"
	}

	privateKeyData, err := os.ReadFile(privateKeyPath)
	if err != nil {
		return fmt.Errorf("failed to read private key from %s: %w", privateKeyPath, err)
	}

	githubAppPrivateKey, err = jwt.ParseRSAPrivateKeyFromPEM(privateKeyData)
	if err != nil {
		return fmt.Errorf("failed to parse private key: %w", err)
	}

	// Initialize HTTP client with timeout
	httpClient = &http.Client{
		Timeout: 30 * time.Second,
	}

	return nil
}

func handleHealthz(w http.ResponseWriter, r *http.Request) {
	w.WriteHeader(http.StatusOK)
	if _, err := w.Write([]byte("OK")); err != nil {
		log.Printf("failed to write healthz response: %v", err)
	}
}

func handleStatus(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		respondError(w, http.StatusMethodNotAllowed, "Method not allowed")
		return
	}

	// Debug log incoming request
	if debugLogging {
		logIncomingRequest(r)
	}

	// Limit request body size to prevent DoS attacks (1MB max)
	r.Body = http.MaxBytesReader(w, r.Body, 1<<20)

	// Parse request body
	var req StatusRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		respondError(w, http.StatusBadRequest, fmt.Sprintf("Invalid request body: %v", err))
		return
	}

	// Debug log parsed request
	if debugLogging {
		reqJSON, _ := json.MarshalIndent(req, "", "  ")
		log.Printf("DEBUG: Parsed request body:\n%s", string(reqJSON))
	}

	// Validate request
	if err := validateRequest(&req); err != nil {
		respondError(w, http.StatusBadRequest, err.Error())
		return
	}

	// Parse owner and repo from repo_url
	owner, repo, err := parseRepoURL(req.RepoURL)
	if err != nil {
		respondError(w, http.StatusBadRequest, fmt.Sprintf("Invalid repo_url: %v", err))
		return
	}

	if debugLogging {
		log.Printf("DEBUG: Parsed repository: owner=%s, repo=%s", owner, repo)
	}

	// Create GitHub App JWT
	appJWT, err := createGitHubAppJWT()
	if err != nil {
		log.Printf("Failed to create GitHub App JWT: %v", err)
		respondError(w, http.StatusInternalServerError, "Failed to authenticate with GitHub")
		return
	}

	// Get installation ID for the repository
	installationID, err := getInstallationID(appJWT, owner, repo)
	if err != nil {
		log.Printf("Failed to get installation ID for %s/%s: %v", owner, repo, err)
		respondError(w, http.StatusNotFound, fmt.Sprintf("GitHub App not installed on repository %s/%s", owner, repo))
		return
	}

	if debugLogging {
		log.Printf("DEBUG: Found installation ID: %d for %s/%s", installationID, owner, repo)
	}

	// Get installation access token
	installationToken, err := getInstallationToken(appJWT, installationID)
	if err != nil {
		log.Printf("Failed to get installation token for installation %d: %v", installationID, err)
		respondError(w, http.StatusInternalServerError, "Failed to get installation token")
		return
	}

	// Create commit status
	if err := createCommitStatus(installationToken, owner, repo, &req); err != nil {
		log.Printf("Failed to create commit status for %s/%s@%s: %v", owner, repo, req.SHA, err)
		respondError(w, http.StatusInternalServerError, fmt.Sprintf("Failed to create commit status: %v", err))
		return
	}

	log.Printf("Successfully created commit status for %s/%s@%s (state: %s, context: %s)", owner, repo, req.SHA, req.State, req.Context)
	respondSuccess(w, "Commit status created successfully")
}

func handleWorkflow(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		respondError(w, http.StatusMethodNotAllowed, "Method not allowed")
		return
	}

	// Debug log incoming request
	if debugLogging {
		logIncomingRequest(r)
	}

	// Limit request body size to prevent DoS attacks (1MB max)
	r.Body = http.MaxBytesReader(w, r.Body, 1<<20)

	// Parse request body
	var event WorkflowEvent
	if err := json.NewDecoder(r.Body).Decode(&event); err != nil {
		respondError(w, http.StatusBadRequest, fmt.Sprintf("Invalid request body: %v", err))
		return
	}

    // Compute if missing or wrong
    phase := normalizeWorkflowPhase(event.Labels, event.Status)
    event.Phase = phase
    event.Event = eventFromPhase(phase)

	// Debug log parsed request
	if debugLogging {
		eventJSON, _ := json.MarshalIndent(event, "", "  ")
		log.Printf("DEBUG: Parsed workflow event:\n%s", string(eventJSON))
	}

	// Validate workflow event
	if err := validateWorkflowEvent(&event); err != nil {
		respondError(w, http.StatusBadRequest, err.Error())
		return
	}

// 	// Extract commit SHA from labels
// 	commitSHA, ok := event.Labels["calypr.io/commit-sha"]
// 	if !ok || commitSHA == "" {
// 		respondError(w, http.StatusBadRequest, "Missing or empty calypr.io/commit-sha label")
// 		return
// 	}

    if event.CommitSha == "" {
		respondError(w, http.StatusBadRequest, "Missing or empty calypr.io/commit-sha label")
		return
    }
    commitSHA := event.CommitSha

	// Extract repo URL from annotations (preferred) or construct from labels
	// Annotations are used because Kubernetes labels cannot contain : or / characters
	repoURL := strings.TrimSpace(event.RepoURL)
	if repoURL == "" {
		respondError(w, http.StatusBadRequest, "Missing repoURL in workflow event payload")
		return
	}

	// Map workflow phase to GitHub status state
	state := mapWorkflowPhaseToGitHubState(event.Phase)
	
	// Create context based on workflow name and namespace
	context := fmt.Sprintf("argo-workflows/%s/%s", event.Namespace, event.Workflow)
	
	// Create description based on event type
	description := fmt.Sprintf("Workflow %s", strings.ToLower(event.Phase))
	
	// Use target URL from event payload (composed in the ClusterWorkflowTemplate)
	// If empty, the GitHub status will be created without a link to the workflow UI
	targetURL := event.TargetURL
	if targetURL == "" && debugLogging {
		log.Printf("DEBUG: target_url is empty in workflow event, status will not have a link to workflow UI")
	}

	// Create status request from workflow event
	statusReq := StatusRequest{
		RepoURL:     repoURL,
		SHA:         commitSHA,
		State:       state,
		Context:     context,
		TargetURL:   targetURL,
		Description: description,
	}

	// Parse owner and repo from repo_url
	owner, repo, err := parseRepoURL(statusReq.RepoURL)
	if err != nil {
		respondError(w, http.StatusBadRequest, fmt.Sprintf("Invalid repo_url: %v", err))
		return
	}

	if debugLogging {
		log.Printf("DEBUG: Workflow event mapped to status: owner=%s, repo=%s, sha=%s, state=%s, context=%s",
			owner, repo, commitSHA, state, context)
	}

	// Create GitHub App JWT
	appJWT, err := createGitHubAppJWT()
	if err != nil {
		log.Printf("Failed to create GitHub App JWT: %v", err)
		respondError(w, http.StatusInternalServerError, "Failed to authenticate with GitHub")
		return
	}

	// Get installation ID for the repository
	installationID, err := getInstallationID(appJWT, owner, repo)
	if err != nil {
		log.Printf("Failed to get installation ID for %s/%s: %v", owner, repo, err)
		respondError(w, http.StatusNotFound, fmt.Sprintf("GitHub App not installed on repository %s/%s", owner, repo))
		return
	}

	if debugLogging {
		log.Printf("DEBUG: Found installation ID: %d for %s/%s", installationID, owner, repo)
	}

	// Get installation access token
	installationToken, err := getInstallationToken(appJWT, installationID)
	if err != nil {
		log.Printf("Failed to get installation token for installation %d: %v", installationID, err)
		respondError(w, http.StatusInternalServerError, "Failed to get installation token")
		return
	}

	// Create commit status
	if err := createCommitStatus(installationToken, owner, repo, &statusReq); err != nil {
		log.Printf("Failed to create commit status for %s/%s@%s: %v", owner, repo, commitSHA, err)
		respondError(w, http.StatusInternalServerError, fmt.Sprintf("Failed to create commit status: %v", err))
		return
	}

	log.Printf("Successfully created commit status for workflow %s/%s: %s/%s@%s (state: %s, context: %s)",
		event.Namespace, event.Workflow, owner, repo, commitSHA, state, context)
	respondSuccess(w, "Workflow notification processed successfully")
}

func validateWorkflowEvent(event *WorkflowEvent) error {
	if event.Kind != "workflow" {
		return fmt.Errorf("kind must be 'workflow'")
	}
	if event.Event == "" {
		return fmt.Errorf("event is required")
	}
	if event.Workflow == "" {
		return fmt.Errorf("workflowName is required")
	}
	if event.Namespace == "" {
		return fmt.Errorf("namespace is required")
	}
	if event.Phase == "" {
		return fmt.Errorf("phase is required")
	}
	if event.Labels == nil {
		return fmt.Errorf("labels is required")
	}
	if strings.TrimSpace(event.RepoURL) == "" {
		return fmt.Errorf("repoURL is required")
	}
	return nil
}

func mapWorkflowPhaseToGitHubState(phase string) string {
	switch strings.ToLower(phase) {
	case "succeeded":
		return "success"
	case "failed", "error":
		return "failure"
	case "running", "pending":
		return "pending"
	default:
		return "error"
	}
}

func validateRequest(req *StatusRequest) error {
	if req.RepoURL == "" {
		return fmt.Errorf("repo_url is required")
	}
	if req.SHA == "" {
		return fmt.Errorf("sha is required")
	}
	if req.State == "" {
		return fmt.Errorf("state is required")
	}
	validStates := map[string]bool{"error": true, "failure": true, "pending": true, "success": true}
	if !validStates[req.State] {
		return fmt.Errorf("state must be one of: error, failure, pending, success")
	}
	if req.Context == "" {
		return fmt.Errorf("context is required")
	}
	return nil
}

func parseRepoURL(repoURL string) (owner, repo string, err error) {
	// Handle various GitHub URL formats:
	// - https://github.com/owner/repo
	// - https://github.com/owner/repo.git
	// - git@github.com:owner/repo.git
	// - owner/repo

	repoURL = strings.TrimSpace(repoURL)
	repoURL = strings.TrimSuffix(repoURL, ".git")

	if strings.HasPrefix(repoURL, "git@github.com:") {
		// SSH format: git@github.com:owner/repo
		repoURL = strings.TrimPrefix(repoURL, "git@github.com:")
		parts := strings.Split(repoURL, "/")
		if len(parts) == 2 {
			return parts[0], parts[1], nil
		}
	} else if strings.Contains(repoURL, "github.com/") {
		// HTTPS format: https://github.com/owner/repo
		u, err := url.Parse(repoURL)
		if err == nil && u.Path != "" {
			pathParts := strings.Split(strings.Trim(u.Path, "/"), "/")
			if len(pathParts) >= 2 {
				return pathParts[0], pathParts[1], nil
			}
		}
	} else if strings.Count(repoURL, "/") == 1 {
		// Simple format: owner/repo
		parts := strings.Split(repoURL, "/")
		return parts[0], parts[1], nil
	}

	return "", "", fmt.Errorf("could not parse owner and repo from URL: %s", repoURL)
}

func createGitHubAppJWT() (string, error) {
	now := time.Now()
	claims := jwt.RegisteredClaims{
		IssuedAt:  jwt.NewNumericDate(now),
		ExpiresAt: jwt.NewNumericDate(now.Add(10 * time.Minute)),
		Issuer:    strconv.FormatInt(githubAppID, 10),
	}

	token := jwt.NewWithClaims(jwt.SigningMethodRS256, claims)
	return token.SignedString(githubAppPrivateKey)
}

func getInstallationID(appJWT, owner, repo string) (int64, error) {
	// URL encode owner and repo to prevent path injection
	apiURL := fmt.Sprintf("https://api.github.com/repos/%s/%s/installation",
		url.PathEscape(owner), url.PathEscape(repo))
	req, err := http.NewRequestWithContext(context.Background(), http.MethodGet, apiURL, nil)
	if err != nil {
		return 0, err
	}

	req.Header.Set("Authorization", "Bearer "+appJWT)
	req.Header.Set("Accept", "application/vnd.github+json")
	req.Header.Set("X-GitHub-Api-Version", "2022-11-28")

	// Log outgoing request in DEBUG mode
	logOutgoingRequest(req, "Get Installation ID")

	resp, err := httpClient.Do(req)
	if err != nil {
		return 0, err
	}
	defer resp.Body.Close()

	// Log response in DEBUG mode
	logOutgoingResponse(resp, "Get Installation ID")

	if resp.StatusCode != http.StatusOK {
		return 0, fmt.Errorf("GitHub API returned status %d", resp.StatusCode)
	}

	// Limit response body size to prevent DoS (1MB max)
	limitedReader := io.LimitReader(resp.Body, 1<<20)
	var installation struct {
		ID int64 `json:"id"`
	}
	if err := json.NewDecoder(limitedReader).Decode(&installation); err != nil {
		return 0, err
	}

	return installation.ID, nil
}

func getInstallationToken(appJWT string, installationID int64) (string, error) {
	apiURL := fmt.Sprintf("https://api.github.com/app/installations/%d/access_tokens", installationID)
	req, err := http.NewRequestWithContext(context.Background(), http.MethodPost, apiURL, nil)
	if err != nil {
		return "", err
	}

	req.Header.Set("Authorization", "Bearer "+appJWT)
	req.Header.Set("Accept", "application/vnd.github+json")
	req.Header.Set("X-GitHub-Api-Version", "2022-11-28")

	// Log outgoing request in DEBUG mode
	logOutgoingRequest(req, "Get Installation Token")

	resp, err := httpClient.Do(req)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()

	// Log response in DEBUG mode
	logOutgoingResponse(resp, "Get Installation Token")

	if resp.StatusCode != http.StatusCreated {
		return "", fmt.Errorf("GitHub API returned status %d", resp.StatusCode)
	}

	// Limit response body size to prevent DoS (1MB max)
	limitedReader := io.LimitReader(resp.Body, 1<<20)
	var tokenResp struct {
		Token string `json:"token"`
	}
	if err := json.NewDecoder(limitedReader).Decode(&tokenResp); err != nil {
		return "", err
	}

	if debugLogging {
		log.Printf("DEBUG: Successfully obtained installation token (length: %d)", len(tokenResp.Token))
	}

	return tokenResp.Token, nil
}

func createCommitStatus(installationToken, owner, repo string, req *StatusRequest) error {
	ctx := context.Background()
	client := github.NewClient(httpClient).WithAuthToken(installationToken)

	status := &github.RepoStatus{
		State:       &req.State,
		Context:     &req.Context,
		Description: &req.Description,
	}

	if req.TargetURL != "" {
		status.TargetURL = &req.TargetURL
	}

	if debugLogging {
		log.Printf("DEBUG: Creating commit status for %s/%s@%s", owner, repo, req.SHA)
		log.Printf("DEBUG: Status details: state=%s, context=%s, description=%s, target_url=%s",
			req.State, req.Context, req.Description, req.TargetURL)
	}

	_, resp, err := client.Repositories.CreateStatus(ctx, owner, repo, req.SHA, status)
	
	if debugLogging && resp != nil {
		log.Printf("DEBUG: Create status response: status=%s", resp.Status)
	}
	
	return err
}

func respondError(w http.ResponseWriter, statusCode int, message string) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(statusCode)
	log.Printf("ERROR: respondError statusCode: %d message %s", statusCode, message)
	if err := json.NewEncoder(w).Encode(StatusResponse{
		Success: false,
		Message: message,
	}); err != nil {
		log.Printf("ERROR: failed to encode error response: %v", err)
	}
}

func respondSuccess(w http.ResponseWriter, message string) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	if err := json.NewEncoder(w).Encode(StatusResponse{
		Success: true,
		Message: message,
	}); err != nil {
		log.Printf("ERROR: failed to encode success response: %v", err)
	}
}

// logIncomingRequest logs details of incoming HTTP requests when DEBUG logging is enabled
func logIncomingRequest(r *http.Request) {
	log.Printf("DEBUG: === Incoming Request ===")
	log.Printf("DEBUG: Method: %s", r.Method)
	log.Printf("DEBUG: URL: %s", r.URL.String())
	log.Printf("DEBUG: Headers:")
	for name, values := range r.Header {
		for _, value := range values {
			// Mask sensitive headers
			if strings.ToLower(name) == "authorization" {
				log.Printf("DEBUG:   %s: [REDACTED]", name)
			} else {
				log.Printf("DEBUG:   %s: %s", name, value)
			}
		}
	}
	
	// Read and log body (we need to restore it for later use)
	// Limit body size to prevent memory exhaustion in debug mode
	if r.Body != nil {
		const maxLogBodySize = 1 << 20 // 1MB
		limitedReader := io.LimitReader(r.Body, maxLogBodySize+1)
		bodyBytes, err := io.ReadAll(limitedReader)
		if err == nil {
			if len(bodyBytes) > maxLogBodySize {
				log.Printf("DEBUG: Body (truncated to %d bytes):\n%s", maxLogBodySize, string(bodyBytes[:maxLogBodySize]))
				// Restore only what we read (truncated)
				r.Body = io.NopCloser(bytes.NewReader(bodyBytes[:maxLogBodySize]))
			} else {
				log.Printf("DEBUG: Body:\n%s", string(bodyBytes))
				// Restore the body for the actual handler
				r.Body = io.NopCloser(bytes.NewReader(bodyBytes))
			}
		}
	}
	log.Printf("DEBUG: === End Incoming Request ===")
}

// logOutgoingRequest logs details of outgoing HTTP requests when DEBUG logging is enabled
func logOutgoingRequest(req *http.Request, description string) {
	if !debugLogging {
		return
	}
	
	log.Printf("DEBUG: === Outgoing Request: %s ===", description)
	log.Printf("DEBUG: Method: %s", req.Method)
	log.Printf("DEBUG: URL: %s", req.URL.String())
	log.Printf("DEBUG: Headers:")
	for name, values := range req.Header {
		for _, value := range values {
			// Mask sensitive headers
			if strings.ToLower(name) == "authorization" {
				log.Printf("DEBUG:   %s: [REDACTED]", name)
			} else {
				log.Printf("DEBUG:   %s: %s", name, value)
			}
		}
	}
	
	// Log body if present
	if req.Body != nil {
		bodyBytes, err := httputil.DumpRequestOut(req, true)
		if err == nil {
			log.Printf("DEBUG: Request dump:\n%s", string(bodyBytes))
		}
	}
	log.Printf("DEBUG: === End Outgoing Request ===")
}

// logOutgoingResponse logs details of outgoing HTTP responses when DEBUG logging is enabled
func logOutgoingResponse(resp *http.Response, description string) {
	if !debugLogging {
		return
	}
	
	log.Printf("DEBUG: === Response: %s ===", description)
	log.Printf("DEBUG: Status: %s", resp.Status)
	log.Printf("DEBUG: Headers:")
	for name, values := range resp.Header {
		for _, value := range values {
			log.Printf("DEBUG:   %s: %s", name, value)
		}
	}
	log.Printf("DEBUG: === End Response ===")
}

// normalizeWorkflowPhase derives a lowercase phase from either labels or status.
// Priority:
//  1) labels["workflows.argoproj.io/phase"]
//  2) status if it's a string (e.g. "Succeeded")
//  3) fallback "unknown"
func normalizeWorkflowPhase(labels map[string]string, status any) string {
	if labels != nil {
		if v := strings.TrimSpace(labels["workflows.argoproj.io/phase"]); v != "" {
			return strings.ToLower(v)
		}
	}

	// Your payload currently sends: "status": "Succeeded"
	if s, ok := status.(string); ok {
		if v := strings.TrimSpace(s); v != "" {
			return strings.ToLower(v)
		}
	}

	return "unknown"
}

// eventFromPhase maps normalized phase to the workflow event string.
func eventFromPhase(phase string) string {
	switch strings.ToLower(strings.TrimSpace(phase)) {
	case "running", "pending":
		return "workflow-pending"
	case "succeeded":
		return "workflow-succeeded"
	case "failed", "error":
		return "workflow-failed"
	default:
		return "workflow-unknown"
	}
}
