local wezterm = require 'wezterm'
local act = wezterm.action
local config = {}

-- ### APPEARANCE ###
config.color_scheme = 'OneHalfDark'
config.window_background_opacity = 0.85
config.initial_cols = 121
config.initial_rows = 29
config.font = wezterm.font_with_fallback {
    'Hack Nerd Font Mono',
    'Fira Code'
}
config.font_size = 12.0

-- ### SO IDENTIFIER ###
-- Windows-specific configuration
if wezterm.target_triple:find('windows') then
    config.default_prog = { 'pwsh.exe', '-NoLogo' }
-- Linux-specific configuration
elseif wezterm.target_triple:find('linux') then
    config.default_prog = {'/bin/zsh'}
-- macOS-specific configuration
elseif wezterm.target_triple:find('macos') then
    config.default_prog = {'/bin/zsh'}
end

-- ### CURSOR EFFECTS ###
config.cursor_trail = true
config.cursor_trail_duration_ms = 200 
config.cursor_trail_animation_speed = 10

-- ### KEYBINDINGS ###
config.disable_default_key_bindings = true
config.keys = {
    -- New tab
    { key = 'T', mods = 'CTRL|SHIFT', action = wezterm.action.SpawnTab 'CurrentPaneDomain' },
    -- Close tab without confirmation
    { key = 'X', mods = 'CTRL|SHIFT', action = wezterm.action.DisableDefaultAssignment },
    { key = 'I', mods = 'CTRL|SHIFT', action = act.CloseCurrentTab{ confirm = true } },
}

return config