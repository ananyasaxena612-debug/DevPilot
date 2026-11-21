#!/usr/bin/env bash
# ==============================================================================
# DevPilot Agent Automated Linux Installer
# Sets up system directories, downloads the agent, performs token enrollment,
# and installs/starts a systemd service.
# ==============================================================================

set -euo pipefail

ENDPOINT=""
TOKEN=""
INTERVAL="10"

print_usage() {
    echo "Usage: sudo bash install.sh --endpoint <DEVPILOT_URL> --token <ENROLLMENT_TOKEN> [--interval <SECONDS>]"
    echo "Example: curl -sSL http://devpilot.local:5000/install.sh | sudo bash -s -- --endpoint http://devpilot.local:5000 --token dpt_abc123"
}

# Parse command line flags
while [[ $# -gt 0 ]]; do
    case "$1" in
        --endpoint|-e)
            ENDPOINT="$2"
            shift 2
            ;;
        --token|-t)
            TOKEN="$2"
            shift 2
            ;;
        --interval|-i)
            INTERVAL="$2"
            shift 2
            ;;
        --help|-h)
            print_usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            print_usage
            exit 1
            ;;
    esac
done

if [[ -z "$ENDPOINT" ]] || [[ -z "$TOKEN" ]]; then
    echo "Error: Both --endpoint and --token parameters are required."
    print_usage
    exit 1
fi

# Ensure running as root
if [[ $EUID -ne 0 ]]; then
    echo "Error: This installer must be run as root (use sudo)."
    exit 1
fi

echo "=================================================="
echo "    DevPilot Linux Monitoring Agent Installer     "
echo "=================================================="
echo "Connecting to DevPilot: $ENDPOINT"

# Check Python 3 availability
if ! command -v python3 &>/dev/null; then
    echo "Python 3 is required. Attempting to install..."
    if command -v apt-get &>/dev/null; then
        apt-get update -y && apt-get install -y python3 python3-pip
    elif command -v yum &>/dev/null; then
        yum install -y python3 python3-pip
    elif command -v dnf &>/dev/null; then
        dnf install -y python3 python3-pip
    else
        echo "Error: Python 3 could not be installed automatically. Please install Python 3 and re-run."
        exit 1
    fi
fi

# Install directories
INSTALL_DIR="/opt/devpilot"
CONFIG_DIR="/etc/devpilot"
mkdir -p "$INSTALL_DIR"
mkdir -p "$CONFIG_DIR"

# Download agent script
AGENT_URL="${ENDPOINT%/}/agent/devpilot_agent.py"
echo "Downloading DevPilot agent script from $AGENT_URL..."

if command -v curl &>/dev/null; then
    curl -sSL "$AGENT_URL" -o "$INSTALL_DIR/devpilot_agent.py"
elif command -v wget &>/dev/null; then
    wget -qO "$INSTALL_DIR/devpilot_agent.py" "$AGENT_URL"
else
    echo "Error: Neither curl nor wget is available."
    exit 1
fi

chmod +x "$INSTALL_DIR/devpilot_agent.py"

# Perform Agent Enrollment
echo "Enrolling server with DevPilot using enrollment token..."
python3 "$INSTALL_DIR/devpilot_agent.py" \
    --enroll \
    --endpoint "$ENDPOINT" \
    --token "$TOKEN" \
    --config "$CONFIG_DIR/agent.conf"

if [[ ! -f "$CONFIG_DIR/agent.conf" ]]; then
    echo "Error: Enrollment failed to generate $CONFIG_DIR/agent.conf."
    exit 1
fi

chmod 600 "$CONFIG_DIR/agent.conf"

# Check if systemd is available
if command -v systemctl &>/dev/null && [ -d /run/systemd/system ]; then
    echo "Configuring systemd service..."
    cat << EOF > /etc/systemd/system/devpilot-agent.service
[Unit]
Description=DevPilot Linux Monitoring Agent
After=network.target

[Service]
Type=simple
User=root
ExecStart=/usr/bin/python3 /opt/devpilot/devpilot_agent.py --daemon --config /etc/devpilot/agent.conf
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=devpilot-agent

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable devpilot-agent
    systemctl restart devpilot-agent

    echo "=================================================="
    echo " SUCCESS: DevPilot Agent is enrolled and running! "
    echo " Status: systemctl status devpilot-agent          "
    echo " Logs:   journalctl -u devpilot-agent -f         "
    echo "=================================================="
else
    echo "Notice: systemd not detected. You can start the agent in background using:"
    echo "nohup python3 /opt/devpilot/devpilot_agent.py --daemon --config /etc/devpilot/agent.conf > /var/log/devpilot-agent.log 2>&1 &"
fi

