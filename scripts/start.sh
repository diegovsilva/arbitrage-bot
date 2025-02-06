#!/bin/bash

# Update and install dependencies
sudo yum update -y
sudo yum install -y python3 git

# Clone the repository (if not already present)
git clone https://github.com/your-repo/arbitrage-bot.git /home/ec2-user/arbitrage-bot

# Navigate to the project directory
cd /home/ec2-user/arbitrage-bot

# Install Python dependencies
pip3 install -r requirements.txt

# Start the websocket server
nohup python3 websocket.py > websocket.log 2>&1 &

# Start the bot
nohup python3 robo.py > robo.log 2>&1 &