local wezterm = require("wezterm")
local act = wezterm.action
local config = wezterm.config_builder()

-- ### APPEARANCE ###
config.color_scheme = "OneDark (base16)"
config.window_background_opacity = 0.8
config.window_decorations = "NONE"
config.enable_wayland = true
config.initial_cols = 121
config.initial_rows = 30
config.font = wezterm.font_with_fallback({
	"Hack Nerd Font Mono",
	"Fira Code",
})
config.font_size = 12.0

-- Helper function to check if a command exists in the PATH
local function is_command_available(cmd)
	local success, stdout, stderr = wezterm.run_child_process({ "/bin/zsh", "-c", "command -v " .. cmd })
	return success
end

-- ### SO IDENTIFIER ###
-- Windows-specific configuration
if wezterm.target_triple:find("windows") then
	config.default_prog = { "pwsh.exe", "-NoLogo" }
-- Linux-specific configuration
elseif wezterm.target_triple:find("linux") then
	-- Check for Zellij availability before setting it as default_prog
	if is_command_available("zellij") then
		config.default_prog = { "zellij", "attach", "--create" }
	else
		config.default_prog = { "/bin/zsh" }
	end
-- macOS-specific configuration
elseif wezterm.target_triple:find("macos") then
	config.default_prog = { "/bin/zsh" }
end

-- ### KEYBINDINGS ###
config.keys = {
	-- Close tab without confirmation
	{ key = "X", mods = "CTRL|SHIFT", action = act.CloseCurrentTab({ confirm = false }) },
}

return config