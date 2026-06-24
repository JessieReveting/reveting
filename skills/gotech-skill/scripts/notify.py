#!/usr/bin/env python3
"""
Notification helper for macOS.
Import this module from other scripts to send macOS notifications.

Usage:
    from notify import notify, notify_critical, notify_success
    
    notify("Title", "Subtitle text")
    notify_critical("Warning!", "Something went wrong")
    notify_success("Done!", "Task completed successfully")
"""

import subprocess
import sys
import os


def notify(title, subtitle="", sound="default"):
    """Send a macOS notification via osascript.
    
    Args:
        title: Main notification title
        subtitle: Secondary text (optional)
        sound: Sound name (default: 'default', use 'Glass', 'Basso', 'Blow', 'Frog', 'Funk', 'Glass', 'Hero', 'Morse', 'Ping', 'Pop', 'Purr', 'Sosumi', 'Submarine', 'Tink')
    """
    script = f'''
    display notification "{subtitle}" with title "{title}" sound name "{sound}"
    '''
    try:
        subprocess.run(
            ["osascript", "-e", script.strip()],
            check=True,
            capture_output=True,
            text=True
        )
        return True
    except subprocess.CalledProcessError as e:
        print(f"[notify] Failed to send notification: {e.stderr}", file=sys.stderr)
        return False


def notify_critical(title, subtitle=""):
    """Send a macOS notification with critical alert sound.
    
    Args:
        title: Main notification title
        subtitle: Secondary text (optional)
    """
    return notify(title, subtitle, sound="Basso")


def notify_success(title, subtitle=""):
    """Send a macOS notification with glass sound.
    
    Args:
        title: Main notification title
        subtitle: Secondary text (optional)
    """
    return notify(title, subtitle, sound="Glass")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 notify.py <title> [subtitle] [sound]")
        print("  sound: default, Glass, Basso, Blow, Frog, Funk, Hero, Morse, Ping, Pop, Purr, Sosumi, Submarine, Tink")
        sys.exit(1)
    
    title = sys.argv[1]
    subtitle = sys.argv[2] if len(sys.argv) > 2 else ""
    sound = sys.argv[3] if len(sys.argv) > 3 else "default"
    
    result = notify(title, subtitle, sound)
    sys.exit(0 if result else 1)
