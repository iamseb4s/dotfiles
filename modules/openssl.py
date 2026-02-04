from modules.base import Module

class OpenSSLModule(Module):
    id = "openssl"
    label = "OpenSSL"
    description = "OpenSSL libraries and headers for development"
    category = "Infrastructure"
    
    package_name = {
        "arch": "openssl",
        "ubuntu": "openssl"
    }
