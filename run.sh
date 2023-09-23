#!/bin/bash
sudo tmux kill-session -t user_creator
sudo tmux new-session -d -s user_creator "sudo python3 main.py"
