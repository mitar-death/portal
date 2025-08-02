#!/bin/zsh
# Script to clean up pycache, session files, and logs

echo "Cleaning up __pycache__ directories..."
find . -type d -name "__pycache__" -exec rm -rf {} +
find . -type f -name "*.pyc" -delete
find . -type f -name "*.pyo" -delete
find . -type f -name "*.pyd" -delete

echo "Cleaning up session files..."
find . -type d -name "sessions" -exec rm -rf {} +
find . -type f -name "*.session" -delete
find . -type f -name "*.session-journal" -delete
rm -rf storage/sessions/* 2>/dev/null

echo "Cleaning up log files..."
find . -type f -name "*.log" -delete
rm -rf storage/logs/* 2>/dev/null

echo "Done! All cache, session, and log files have been removed."
