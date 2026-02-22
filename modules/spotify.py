from modules.base import Module

class SpotifyModule(Module):
    """
    Module for installing Spotify with window manager integration (spotifywm).
    """
    id = "spotify"
    label = "Spotify"
    category = "Desktop"
    description = "Proprietary music streaming service with window manager fixes."

    package_name = {
        "arch": "spotify spotifywm-git"
    }

    manager = {
        "arch": "yay",
        "default": "system"
    }

    dependencies = {
        "arch": {
            "bin_deps": ["yay"],
            "dot_deps": ["stow"]
        },
        "ubuntu": {
            "dot_deps": ["stow"]
        }
    }
