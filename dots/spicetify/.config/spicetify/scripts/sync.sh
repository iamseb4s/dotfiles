#!/bin/bash

# Base directories
CONF_DIR="$HOME/.config/spicetify"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
THEME_DIR="$CONF_DIR/Themes/sleek"
EXT_DIR="$CONF_DIR/Extensions"
SOURCES_FILE="$SCRIPT_DIR/sources.txt"
SNIPPETS_FILE="$SCRIPT_DIR/snippets.css"

if [ ! -f "$SOURCES_FILE" ]; then
    echo "Error: $SOURCES_FILE not found."
    exit 1
fi

echo "Starting Spicetify synchronization..."

# 1. Sync Theme (Sleek) - Extract URLs from sources.txt
THEME_URLS=$(python3 -c "
import configparser
config = configparser.ConfigParser(interpolation=None)
config.optionxform = str
config.read('$SOURCES_FILE')
print(f\"{config['Theme:Sleek']['user_css']} {config['Theme:Sleek']['color_ini']}\")
")

read -r CSS_URL COLOR_URL <<< "$THEME_URLS"

echo "Downloading Sleek theme base files..."
mkdir -p "$THEME_DIR"
curl -fsSL "$CSS_URL" -o "$THEME_DIR/user.css"
curl -fsSL "$COLOR_URL" -o "$THEME_DIR/color.ini"

# 2. Sync Extensions
echo "Syncing extensions from sources..."
mkdir -p "$EXT_DIR"
python3 -c "
import configparser, urllib.request, os
config = configparser.ConfigParser(interpolation=None)
config.optionxform = str
config.read('$SOURCES_FILE')
for filename, url in config.items('Extensions'):
    print(f'  -> {filename}')
    urllib.request.urlretrieve(url, os.path.join('$EXT_DIR', filename))
"

# 3. Extract Snippets from Marketplace JSON
echo "Processing snippets from Marketplace JSON..."
python3 -c "
import json, urllib.request, configparser
config = configparser.ConfigParser(interpolation=None)
config.optionxform = str
config.read('$SOURCES_FILE')
target = [t.strip() for t in config['Snippets']['list'].split(',')]
url = config['Snippets']['source_json']
try:
    with urllib.request.urlopen(url) as r:
        data = json.loads(r.read().decode())
        with open('$SNIPPETS_FILE', 'w') as f:
            for t in target:
                for s in data:
                    if s['title'] == t:
                        f.write(f'/* --- {t} --- */\n{s[\"code\"]}\n\n')
                        break
except Exception as e:
    print(f'Error processing snippets: {e}')
"

# 4. Inject Snippets with the EXACT separator from your user.css
echo "Injecting snippets with personalized separator..."
cat << 'SEP' >> "$THEME_DIR/user.css"
/*
-----------------
PERSONAL SNIPPETS
-----------------
*/
SEP
cat "$SNIPPETS_FILE" >> "$THEME_DIR/user.css"

echo "Spicetify synchronization completed successfully!"
