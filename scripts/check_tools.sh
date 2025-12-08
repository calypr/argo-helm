#!/bin/bash

# Script to check installed tools and APT installation history
# Usage: ./check_tools_with_apt_history.sh

echo "=== Tool Installation Check with APT History ==="
echo "Date: $(date)"
echo "Hostname: $(hostname)"
echo "========================================"

# Define colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m' # No Color

# Function to check if a command exists and get version
check_tool() {
    local tool=$1
    
    if command -v "$tool" &> /dev/null; then
        echo -e "${GREEN}✓${NC} $tool is installed at: $(which $tool)"
        
        # Try to get version information
        case $tool in
            "docker")
                echo "  Version: $(docker --version 2>/dev/null)"
                ;;
            "kubectl")
                echo "  Version: $(kubectl version --client --short 2>/dev/null || kubectl version --client 2>/dev/null | head -1)"
                ;;
            "helm")
                echo "  Version: $(helm version --short 2>/dev/null || helm version 2>/dev/null | head -1)"
                ;;
            "kind")
                echo "  Version: $(kind version 2>/dev/null)"
                ;;
            "k9s")
                echo "  Version: $(k9s version --short 2>/dev/null || k9s version 2>/dev/null | head -1)"
                ;;
            "stern")
                echo "  Version: $(stern --version 2>/dev/null)"
                ;;
            "jq")
                echo "  Version: $(jq --version 2>/dev/null)"
                ;;
            "git")
                echo "  Version: $(git --version 2>/dev/null)"
                ;;
            "python3")
                echo "  Version: $(python3 --version 2>/dev/null)"
                ;;
            "pytest")
                echo "  Version: $(pytest --version 2>/dev/null | head -1)"
                ;;
            "envsubst")
                echo "  Version: $(envsubst --version 2>/dev/null | head -1)"
                ;;
            "certbot")
                echo "  Version: $(certbot --version 2>/dev/null)"
                ;;
            "go")
                echo "  Version: $(go version 2>/dev/null)"
                ;;
            "gcc")
                echo "  Version: $(gcc --version 2>/dev/null | head -1)"
                ;;
            "curl")
                echo "  Version: $(curl --version 2>/dev/null | head -1)"
                ;;
            "openssl")
                echo "  Version: $(openssl version 2>/dev/null)"
                ;;
            "sqlite3")
                echo "  Version: $(sqlite3 --version 2>/dev/null | head -1)"
                ;;		
            *)
                version_output=$($tool --version 2>/dev/null | head -1)
                if [ -n "$version_output" ]; then
                    echo "  Version: $version_output"
                else
                    echo "  Version: Not available"
                fi
                ;;
        esac
        echo ""
    else
        echo -e "${RED}✗${NC} $tool is NOT installed"
        echo ""
    fi
}

# Function to check APT history
check_apt_history() {
    echo -e "${BLUE}=== APT Installation History ===${NC}"
    
    if ! command -v apt &> /dev/null; then
        echo -e "${YELLOW}APT is not available on this system${NC}"
        
        # Check for other package managers
        if command -v yum &> /dev/null; then
            echo -e "${CYAN}YUM system detected. Checking yum history...${NC}"
            check_yum_history
            return
        elif command -v dnf &> /dev/null; then
            echo -e "${CYAN}DNF system detected. Checking dnf history...${NC}"
            check_dnf_history
            return
        else
            echo "No supported package manager history available"
            return
        fi
    fi
    
    # Show recent APT operations
    echo -e "${CYAN}Recent APT operations:${NC}"
    if [ -f /var/log/apt/history.log ]; then
        echo "From /var/log/apt/history.log (most recent 15 operations):"
        grep -E "^Start-Date|^Commandline|^Install:|^Upgrade:" /var/log/apt/history.log | tail -30 | sed 's/^/  /'
        echo ""
    fi
    
    # Define tools and their common package names in APT
    declare -A tool_packages=(
        ["docker"]="docker.io docker-ce docker-engine containerd.io"
        ["git"]="git git-core"
        ["python3"]="python3 python3-dev python3-pip"
        ["jq"]="jq"
        ["kubectl"]="kubectl"
        ["helm"]="helm"
        ["kind"]="kind"
        ["k9s"]="k9s"
        ["stern"]="stern"
        ["pytest"]="python3-pytest pytest"
        ["envsubst"]="gettext-base gettext"
        ["certbot"]="certbot python3-certbot-nginx python3-certbot-apache"
        ["go"]="golang-go golang"
        ["gcc"]="gcc build-essential"
        ["curl"]="curl"
        ["openssl"]="openssl libssl-dev"
        ["sqlite3"]="sqlite"
    )
    
    echo -e "${CYAN}Searching APT history for tool installations:${NC}"
    
    for tool in "${!tool_packages[@]}"; do
        echo -e "\n${YELLOW}Checking for $tool packages:${NC}"
        packages=${tool_packages[$tool]}
        
        found_any=false
        for package in $packages; do
            # Search in APT history log
            if [ -f /var/log/apt/history.log ]; then
                history_result=$(grep -A5 -B1 "$package" /var/log/apt/history.log 2>/dev/null | grep -E "Start-Date|Install:|Upgrade:" | tail -5)
                if [ -n "$history_result" ]; then
                    echo -e "  ${GREEN}Found $package in APT history:${NC}"
                    echo "$history_result" | sed 's/^/    /'
                    found_any=true
                fi
            fi
            
            # Search in dpkg log
            if [ -f /var/log/dpkg.log ]; then
                dpkg_result=$(grep "install.*$package" /var/log/dpkg.log 2>/dev/null | tail -3)
                if [ -n "$dpkg_result" ]; then
                    echo -e "  ${GREEN}Found $package in dpkg log:${NC}"
                    echo "$dpkg_result" | sed 's/^/    /'
                    found_any=true
                fi
            fi
        done
        
        if [ "$found_any" = false ]; then
            echo -e "  ${RED}No APT installation found for $tool${NC}"
        fi
    done
}

# Function to check YUM history (fallback)
check_yum_history() {
    echo "Recent YUM transactions:"
    yum history list 2>/dev/null | head -15
    echo ""
    
    echo -e "${CYAN}Searching YUM history for development tools:${NC}"
    yum history list | grep -E "(docker|git|python|jq|kubectl|helm|kind|gcc|curl|openssl)" 2>/dev/null || echo "No matching packages found in YUM history"
}

# Function to check DNF history (fallback)
check_dnf_history() {
    echo "Recent DNF transactions:"
    dnf history list 2>/dev/null | head -15
    echo ""
    
    echo -e "${CYAN}Searching DNF history for development tools:${NC}"
    dnf history list | grep -E "(docker|git|python|jq|kubectl|helm|kind|gcc|curl|openssl)" 2>/dev/null || echo "No matching packages found in DNF history"
}

# Function to check installed packages via dpkg
check_installed_packages() {
    echo -e "${BLUE}=== Currently Installed Packages (via dpkg) ===${NC}"
    
    if command -v dpkg &> /dev/null; then
        echo -e "${CYAN}Checking for tool-related packages currently installed:${NC}"
        
        # List of package patterns to search for
        patterns=("docker" "git" "python3" "jq" "kubectl" "helm" "kind" "k9s" "stern" "pytest" "gettext" "certbot" "golang" "gcc" "curl" "openssl" "sqlite")
        
        for pattern in "${patterns[@]}"; do
            installed_packages=$(dpkg -l | grep -i "$pattern" | awk '{print $2, $3}' 2>/dev/null)
            if [ -n "$installed_packages" ]; then
                echo -e "\n${YELLOW}Packages matching '$pattern':${NC}"
                echo "$installed_packages" | sed 's/^/  /'
            fi
        done
    else
        echo "dpkg not available"
    fi
    echo ""
}

# Function to find additional development tools
find_additional_tools() {
    echo -e "${BLUE}=== Additional Development Tools Found ===${NC}"
    
    additional_tools=(
        "aws" "terraform" "ansible" "vagrant" "node" "npm" "yarn" 
        "java" "javac" "mvn" "gradle" "make" "cmake" "g++" 
        "wget" "vim" "nano" "emacs" "tmux" "screen" "htop" "tree"
        "zip" "unzip" "tar" "rsync" "ssh" "scp" "netstat" "ss"
        "systemctl" "journalctl" "crontab" "at" "nohup" "sudo"
        "awk" "sed" "grep" "find" "xargs" "sort" "uniq" "head" "tail"
        "nc" "telnet" "ping" "traceroute" "dig" "nslookup"
        "lsof" "ps" "top" "df" "du" "free" "uptime" "whoami"
    )
    
    echo "Scanning for additional development and system tools:"
    found_additional=()
    
    for tool in "${additional_tools[@]}"; do
        if command -v "$tool" &> /dev/null; then
            found_additional+=("$tool")
        fi
    done
    
    if [ ${#found_additional[@]} -gt 0 ]; then
        echo -e "${GREEN}Additional tools found (${#found_additional[@]} total):${NC}"
        printf '%s\n' "${found_additional[@]}" | column -c 100 | sed 's/^/  /'
    else
        echo "No additional common development tools found"
    fi
    echo ""
}

# Function to check snap packages
check_snap_packages() {
    if command -v snap &> /dev/null; then
        echo -e "${BLUE}=== Snap Packages ===${NC}"
        echo -e "${CYAN}Checking for tools installed via Snap:${NC}"
        
        snap_tools=$(snap list 2>/dev/null | grep -E "(docker|git|kubectl|helm|kind|k9s|stern|go|code)" | awk '{print $1, $2}')
        if [ -n "$snap_tools" ]; then
            echo "$snap_tools" | sed 's/^/  /'
        else
            echo "  No relevant snap packages found"
        fi
        echo ""
    fi
}

# Main execution
echo "Checking for requested tools..."
echo ""

# List of primary tools to check
tools=(
    "kind"
    "jq" 
    "k9s"
    "stern"
    "helm"
    "kubectl"
    "docker"
    "git"
    "pytest"
    "envsubst"
    "python3"
    "certbot"
    "go"
    "gcc"
    "curl"
    "openssl"
    "sqlite3"
)

# Check each tool
for tool in "${tools[@]}"; do
    check_tool "$tool"
done

# Check package manager history
echo ""
check_apt_history

# Check currently installed packages
echo ""
check_installed_packages

# Check snap packages
echo ""
check_snap_packages

# Find additional tools
echo ""
find_additional_tools

# System information
echo -e "${BLUE}=== System Information ===${NC}"
echo "Operating System:"
if [ -f /etc/os-release ]; then
    . /etc/os-release
    echo "  $PRETTY_NAME"
elif [ -f /etc/lsb-release ]; then
    . /etc/lsb-release
    echo "  $DISTRIB_DESCRIPTION"
elif [ -f /etc/debian_version ]; then
    echo "  Debian $(cat /etc/debian_version)"
else
    uname -s
fi

echo "Architecture: $(uname -m)"
echo "Kernel: $(uname -r)"
echo "Uptime: $(uptime -p 2>/dev/null || uptime)"

# Check environment
if [ -f /.dockerenv ]; then
    echo "Environment: Running in Docker container"
elif [ -n "${KUBERNETES_SERVICE_HOST}" ]; then
    echo "Environment: Running in Kubernetes pod"
else
    echo "Environment: Standard Linux instance"
fi

echo ""
echo -e "${BLUE}=== Package Managers Available ===${NC}"
command -v apt &> /dev/null && echo -e "${GREEN}✓${NC} apt $(apt --version 2>/dev/null | head -1)"
command -v dpkg &> /dev/null && echo -e "${GREEN}✓${NC} dpkg $(dpkg --version 2>/dev/null | head -1)"
command -v snap &> /dev/null && echo -e "${GREEN}✓${NC} snap $(snap version 2>/dev/null | head -1)"
command -v pip3 &> /dev/null && echo -e "${GREEN}✓${NC} pip3 $(pip3 --version 2>/dev/null)"
command -v npm &> /dev/null && echo -e "${GREEN}✓${NC} npm $(npm --version 2>/dev/null)"

# Summary
echo ""
echo -e "${BLUE}=== Summary ===${NC}"
installed_count=0
total_count=${#tools[@]}

for tool in "${tools[@]}"; do
    if command -v "$tool" &> /dev/null; then
        ((installed_count++))
    fi
done

echo "Primary tools installed: $installed_count/$total_count"

if [ $installed_count -eq $total_count ]; then
    echo -e "${GREEN}All requested tools are installed!${NC}"
elif [ $installed_count -gt $((total_count / 2)) ]; then
    echo -e "${YELLOW}Most tools are installed.${NC}"
else
    echo -e "${RED}Many tools are missing.${NC}"
fi

echo ""
echo "Script completed at $(date)"


