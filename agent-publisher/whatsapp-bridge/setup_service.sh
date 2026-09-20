#!/bin/bash
set -e

sudo tee /etc/systemd/system/whatsapp-bridge.service > /dev/null << 'EOF'
[Unit]
Description=Bloguito WhatsApp Remote Control Bridge
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/agent-publisher/whatsapp-bridge
ExecStart=/usr/bin/node index.js
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
Environment=NODE_ENV=production
EnvironmentFile=-/home/ubuntu/agent-publisher/whatsapp-bridge/.env

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now whatsapp-bridge.service
sleep 2
sudo systemctl status whatsapp-bridge.service --no-pager
