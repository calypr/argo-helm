package main

import (
	"testing"
)

func TestParseRepoURL(t *testing.T) {
	tests := []struct {
		name      string
		repoURL   string
		wantOwner string
		wantRepo  string
		wantErr   bool
	}{
		{
			name:      "HTTPS URL",
			repoURL:   "https://github.com/calypr/argo-helm",
			wantOwner: "calypr",
			wantRepo:  "argo-helm",
			wantErr:   false,
		},
		{
			name:      "HTTPS URL with .git",
			repoURL:   "https://github.com/owner/repo.git",
			wantOwner: "owner",
			wantRepo:  "repo",
			wantErr:   false,
		},
		{
			name:      "SSH URL",
			repoURL:   "git@github.com:owner/repo.git",
			wantOwner: "owner",
			wantRepo:  "repo",
			wantErr:   false,
		},
		{
			name:      "Simple format",
			repoURL:   "owner/repo",
			wantOwner: "owner",
			wantRepo:  "repo",
			wantErr:   false,
		},
		{
			name:      "Invalid format",
			repoURL:   "invalid",
			wantOwner: "",
			wantRepo:  "",
			wantErr:   true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			owner, repo, err := parseRepoURL(tt.repoURL)
			if (err != nil) != tt.wantErr {
				t.Errorf("parseRepoURL() error = %v, wantErr %v", err, tt.wantErr)
				return
			}
			if owner != tt.wantOwner {
				t.Errorf("parseRepoURL() owner = %v, want %v", owner, tt.wantOwner)
			}
			if repo != tt.wantRepo {
				t.Errorf("parseRepoURL() repo = %v, want %v", repo, tt.wantRepo)
			}
		})
	}
}

func TestValidateRequest(t *testing.T) {
	tests := []struct {
		name    string
		req     StatusRequest
		wantErr bool
	}{
		{
			name: "Valid request",
			req: StatusRequest{
				RepoURL: "https://github.com/owner/repo",
				SHA:     "abc123",
				State:   "success",
				Context: "argocd/test",
			},
			wantErr: false,
		},
		{
			name: "Missing repo_url",
			req: StatusRequest{
				SHA:     "abc123",
				State:   "success",
				Context: "argocd/test",
			},
			wantErr: true,
		},
		{
			name: "Missing sha",
			req: StatusRequest{
				RepoURL: "https://github.com/owner/repo",
				State:   "success",
				Context: "argocd/test",
			},
			wantErr: true,
		},
		{
			name: "Missing state",
			req: StatusRequest{
				RepoURL: "https://github.com/owner/repo",
				SHA:     "abc123",
				Context: "argocd/test",
			},
			wantErr: true,
		},
		{
			name: "Invalid state",
			req: StatusRequest{
				RepoURL: "https://github.com/owner/repo",
				SHA:     "abc123",
				State:   "invalid",
				Context: "argocd/test",
			},
			wantErr: true,
		},
		{
			name: "Missing context",
			req: StatusRequest{
				RepoURL: "https://github.com/owner/repo",
				SHA:     "abc123",
				State:   "success",
			},
			wantErr: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := validateRequest(&tt.req)
			if (err != nil) != tt.wantErr {
				t.Errorf("validateRequest() error = %v, wantErr %v", err, tt.wantErr)
			}
		})
	}
}

func TestValidateWorkflowEvent(t *testing.T) {
	tests := []struct {
		name    string
		event   WorkflowEvent
		wantErr bool
	}{
		{
			name: "Valid workflow event",
			event: WorkflowEvent{
				Kind:      "workflow",
				Event:     "workflow-succeeded",
				Workflow:  "test-workflow",
				Namespace: "default",
				Phase:     "Succeeded",
				Labels: map[string]string{
					"calypr.io/commit-sha": "abc123",
					"calypr.io/repo":       "calypr/argo-helm",
				},
				Annotations: map[string]string{},
			},
			wantErr: false,
		},
		{
			name: "Missing kind",
			event: WorkflowEvent{
				Event:     "workflow-succeeded",
				Workflow:  "test-workflow",
				Namespace: "default",
				Phase:     "Succeeded",
				Labels:    map[string]string{},
			},
			wantErr: true,
		},
		{
			name: "Wrong kind",
			event: WorkflowEvent{
				Kind:      "task",
				Event:     "workflow-succeeded",
				Workflow:  "test-workflow",
				Namespace: "default",
				Phase:     "Succeeded",
				Labels:    map[string]string{},
			},
			wantErr: true,
		},
		{
			name: "Missing event",
			event: WorkflowEvent{
				Kind:      "workflow",
				Workflow:  "test-workflow",
				Namespace: "default",
				Phase:     "Succeeded",
				Labels:    map[string]string{},
			},
			wantErr: true,
		},
		{
			name: "Missing workflow name",
			event: WorkflowEvent{
				Kind:      "workflow",
				Event:     "workflow-succeeded",
				Namespace: "default",
				Phase:     "Succeeded",
				Labels:    map[string]string{},
			},
			wantErr: true,
		},
		{
			name: "Missing namespace",
			event: WorkflowEvent{
				Kind:     "workflow",
				Event:    "workflow-succeeded",
				Workflow: "test-workflow",
				Phase:    "Succeeded",
				Labels:   map[string]string{},
			},
			wantErr: true,
		},
		{
			name: "Missing phase",
			event: WorkflowEvent{
				Kind:      "workflow",
				Event:     "workflow-succeeded",
				Workflow:  "test-workflow",
				Namespace: "default",
				Labels:    map[string]string{},
			},
			wantErr: true,
		},
		{
			name: "Nil labels",
			event: WorkflowEvent{
				Kind:      "workflow",
				Event:     "workflow-succeeded",
				Workflow:  "test-workflow",
				Namespace: "default",
				Phase:     "Succeeded",
			},
			wantErr: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := validateWorkflowEvent(&tt.event)
			if (err != nil) != tt.wantErr {
				t.Errorf("validateWorkflowEvent() error = %v, wantErr %v", err, tt.wantErr)
			}
		})
	}
}

func TestMapWorkflowPhaseToGitHubState(t *testing.T) {
	tests := []struct {
		name      string
		phase     string
		wantState string
	}{
		{
			name:      "Succeeded phase",
			phase:     "Succeeded",
			wantState: "success",
		},
		{
			name:      "Failed phase",
			phase:     "Failed",
			wantState: "failure",
		},
		{
			name:      "Error phase",
			phase:     "Error",
			wantState: "failure",
		},
		{
			name:      "Running phase",
			phase:     "Running",
			wantState: "pending",
		},
		{
			name:      "Pending phase",
			phase:     "Pending",
			wantState: "pending",
		},
		{
			name:      "Unknown phase",
			phase:     "Unknown",
			wantState: "error",
		},
		{
			name:      "Lowercase succeeded",
			phase:     "succeeded",
			wantState: "success",
		},
		{
			name:      "Lowercase failed",
			phase:     "failed",
			wantState: "failure",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			state := mapWorkflowPhaseToGitHubState(tt.phase)
			if state != tt.wantState {
				t.Errorf("mapWorkflowPhaseToGitHubState() = %v, want %v", state, tt.wantState)
			}
		})
	}
}
