package main

import (
	"context"
	"crypto/rsa"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
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

type StatusResponse struct {
	Success bool   `json:"success"`
	Message string `json:"message"`
}

var (
	githubAppID         int64
	githubAppPrivateKey *rsa.PrivateKey
	httpClient          *http.Client
)

func main() {
	// Load configuration
	if err := loadConfig(); err != nil {
		log.Fatalf("Failed to load configuration: %v", err)
	}

	// Setup HTTP server
	http.HandleFunc("/status", handleStatus)
	http.HandleFunc("/healthz", handleHealthz)

	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
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
	w.Write([]byte("OK"))
}

func handleStatus(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		respondError(w, http.StatusMethodNotAllowed, "Method not allowed")
		return
	}

	// Limit request body size to prevent DoS attacks (1MB max)
	r.Body = http.MaxBytesReader(w, r.Body, 1<<20)

	// Parse request body
	var req StatusRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		respondError(w, http.StatusBadRequest, fmt.Sprintf("Invalid request body: %v", err))
		return
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

	resp, err := httpClient.Do(req)
	if err != nil {
		return 0, err
	}
	defer resp.Body.Close()

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

	resp, err := httpClient.Do(req)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()

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

	_, _, err := client.Repositories.CreateStatus(ctx, owner, repo, req.SHA, status)
	return err
}

func respondError(w http.ResponseWriter, statusCode int, message string) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(statusCode)
	json.NewEncoder(w).Encode(StatusResponse{
		Success: false,
		Message: message,
	})
}

func respondSuccess(w http.ResponseWriter, message string) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(StatusResponse{
		Success: true,
		Message: message,
	})
}
