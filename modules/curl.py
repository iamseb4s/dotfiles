from modules.base import Module

class CurlModule(Module):
    id = "curl"
    label = "cURL"
    description = "Command line tool for transferring data with URLs"
    category = "Infrastructure"
    
    package_name = {
        "arch": "curl",
        "ubuntu": "curl"
    }
