#!/bin/bash
# Validate GitHub Copilot instruction files
# This script checks that all instruction files have proper frontmatter

set -euo pipefail

INSTRUCTIONS_DIR=".github/instructions"
ERRORS=0

echo "🔍 Validating Copilot instruction files..."
echo ""

# Check if instructions directory exists
if [[ ! -d "${INSTRUCTIONS_DIR}" ]]; then
    echo "❌ Error: Instructions directory not found: ${INSTRUCTIONS_DIR}"
    exit 1
fi

# Find all .instructions.md files
shopt -s nullglob
instruction_files=("${INSTRUCTIONS_DIR}"/*.instructions.md)

if [[ ${#instruction_files[@]} -eq 0 ]]; then
    echo "⚠️  Warning: No instruction files found in ${INSTRUCTIONS_DIR}"
    exit 0
fi

echo "Found ${#instruction_files[@]} instruction file(s)"
echo ""

# Validate each instruction file
for file in "${instruction_files[@]}"; do
    filename=$(basename "$file")
    echo "Checking ${filename}..."
    
    # Check if file starts with frontmatter
    if ! head -n 1 "$file" | grep -q "^---$"; then
        echo "  ❌ Missing frontmatter opening delimiter"
        ((ERRORS++))
        continue
    fi
    
    # Check for description field
    if ! head -n 10 "$file" | grep -q "^description:"; then
        echo "  ❌ Missing 'description' field in frontmatter"
        ((ERRORS++))
    else
        echo "  ✅ Has description field"
    fi
    
    # Check for applyTo field
    if ! head -n 10 "$file" | grep -q "^applyTo:"; then
        echo "  ❌ Missing 'applyTo' field in frontmatter"
        ((ERRORS++))
    else
        echo "  ✅ Has applyTo field"
    fi
    
    # Check for closing frontmatter delimiter
    if ! head -n 10 "$file" | grep -A 1 "^description:" | tail -n +2 | grep -q "^---$" && \
       ! head -n 10 "$file" | grep -A 1 "^applyTo:" | tail -n +2 | grep -q "^---$"; then
        # Check more lines for closing delimiter
        if ! head -n 15 "$file" | tail -n +2 | grep -q "^---$"; then
            echo "  ❌ Missing frontmatter closing delimiter"
            ((ERRORS++))
        else
            echo "  ✅ Has frontmatter closing delimiter"
        fi
    else
        echo "  ✅ Has frontmatter closing delimiter"
    fi
    
    # Check file has content beyond frontmatter
    line_count=$(wc -l < "$file")
    if [[ $line_count -lt 20 ]]; then
        echo "  ⚠️  Warning: File seems very short (${line_count} lines)"
    else
        echo "  ✅ Has substantial content (${line_count} lines)"
    fi
    
    echo ""
done

# Summary
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [[ $ERRORS -eq 0 ]]; then
    echo "✅ All instruction files are valid!"
    exit 0
else
    echo "❌ Found ${ERRORS} error(s) in instruction files"
    exit 1
fi
