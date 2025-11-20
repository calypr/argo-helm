# Add Authentication Support for Git Clone in Nextflow Repo Runner

## Description

The `nextflow-repo-runner` WorkflowTemplate currently performs unauthenticated git clone operations, which has several limitations and security concerns:

1. **Private Repository Support**: The current implementation cannot clone private repositories since it doesn't use authentication credentials
2. **Security Risk**: Cloning arbitrary URLs without validation could pose security risks
3. **Missing URL Validation**: No validation is performed on repository URLs before cloning

## Current Implementation

The git clone operation in `helm/argo-stack/templates/workflows/workflowtemplate-nextflow-repo-runner.yaml` (line 47-48):

```yaml
echo "Cloning repo: {{workflow.parameters.repo-url}}"
git clone {{workflow.parameters.repo-url}} repo
cd repo
git checkout {{workflow.parameters.revision}}
```

## Proposed Solution

Add support for authenticated git clone operations by:

1. **Utilize Existing GitHub Credentials**: The `RepoRegistration` CRD already references GitHub credentials via the `githubSecretName` field. These credentials should be leveraged for git clone operations.

2. **Implement Authenticated Clone**: Modify the workflow template to:
   - Mount the GitHub credentials secret referenced in the RepoRegistration
   - Use the credentials for HTTPS-based authentication (e.g., `https://<token>@github.com/org/repo.git`)
   - Or configure SSH-based authentication if SSH keys are provided

3. **Add URL Validation**: 
   - Validate that repository URLs match expected patterns (already enforced in CRD: `pattern: '^https://.+\.git$'`)
   - Consider adding allowlist/denylist for repository sources if needed

4. **Support Both Public and Private Repos**:
   - Maintain backward compatibility for public repositories
   - Enable seamless cloning of private repositories using the provided credentials

## Benefits

- Enable support for private repositories
- Improve security by validating repository sources
- Leverage existing GitHub credential infrastructure defined in RepoRegistration
- Maintain consistency with the rest of the authentication model

## References

- Original PR: #39
- Review Comment: https://github.com/calypr/argo-helm/pull/39#discussion_r2544005828
- Related File: `helm/argo-stack/templates/workflows/workflowtemplate-nextflow-repo-runner.yaml`
- Related CRD: `helm/argo-stack/crds/repo-registration-crd.yaml` (line 102-106: `githubSecretName`)

## Acceptance Criteria

- [ ] Git clone operations support authentication using credentials from `githubSecretName`
- [ ] Private repositories can be successfully cloned
- [ ] Public repositories continue to work without breaking changes
- [ ] Repository URL validation is implemented
- [ ] Documentation is updated with authentication setup instructions
- [ ] Tests verify both public and private repository cloning scenarios
