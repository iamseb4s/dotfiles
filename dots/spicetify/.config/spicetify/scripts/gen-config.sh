#!/bin/bash

# Generates ~/.config/spicetify/config-xpui.ini with platform-specific paths.
# The file is machine-specific and gitignored; run this after spicetify
# updates overwrite the paths.
# The [Backup] section is intentionally omitted: 'spicetify backup apply'
# writes it automatically with the installed Spotify/spicetify versions.

CONFIG_FILE="$HOME/.config/spicetify/config-xpui.ini"

# Platform-specific paths
if [[ "$(uname)" == "Darwin" ]]; then
    PREFS_PATH="$HOME/Library/Application Support/Spotify/prefs"
    SPOTIFY_PATH="/Applications/Spotify.app/Contents/Resources"
else
    PREFS_PATH="$HOME/.config/spotify/prefs"
    SPOTIFY_PATH="/opt/spotify/"
fi

# Auto-discover extensions installed in the Extensions folder
EXT_DIR="$HOME/.config/spicetify/Extensions"
EXTENSIONS=""
if [[ -d "$EXT_DIR" ]]; then
    EXTENSIONS=$(ls "$EXT_DIR" 2>/dev/null | grep -E '\.(js|mjs)$' | sort | paste -sd'|' -)
fi

cat > "$CONFIG_FILE" << EOF
[Setting]
prefs_path             = $PREFS_PATH
current_theme          = sleek
inject_theme_js        = 1
replace_colors         = 1
spotify_launch_flags   = 
spotify_path           = $SPOTIFY_PATH
color_scheme           = RosePine
inject_css             = 1
overwrite_assets       = 0
check_spicetify_update = 1
always_enable_devtools = 0

[Preprocesses]
disable_sentry     = 1
disable_ui_logging = 1
remove_rtl_rule    = 1
expose_apis        = 1

[AdditionalOptions]
sidebar_config        = 0
home_config           = 1
experimental_features = 1
extensions            = $EXTENSIONS
custom_apps           = marketplace

[Patch]
EOF

echo "Generated $CONFIG_FILE"