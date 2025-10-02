FROM archlinux:latest

ENV TERM=xterm-256color

# Update the system and install basic dependencies we'll need for testing
RUN pacman -Syu --noconfirm git sudo base-devel

# Create a test user to avoid running everything as root and to simulate a real environment
RUN useradd -m -s /bin/bash tester && \
    echo "tester ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers

# Switch to the test user
USER tester
WORKDIR /home/tester