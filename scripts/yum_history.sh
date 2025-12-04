echo "=== Quick Tool & YUM History Check ===" && \
for tool in kind jq k9s stern helm kubectl docker git pytest envsubst python3 certbot go gcc  curl openssl; do 
  if command -v "$tool" &> /dev/null; then 
    echo "✓ $tool: $(command -v $tool)"; 
  else 
    echo "✗ $tool: NOT FOUND"; 
  fi; 
done && \
echo -e "\n=== Recent YUM History ===" && \
yum history list 2>/dev/null | head -10 && \
echo -e "\n=== YUM Packages for Development Tools ===" && \
yum history packages-list docker git python3 jq 2>/dev/null | grep -E "Install|Update" | head -10
