[![](https://img.shields.io/github/release/Aleks130699/ha-fpp/all.svg?style=for-the-badge)](https://github.com/Aleks130699/ha-fpp/releases)
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge)](https://github.com/custom-components/hacs)
[![](https://img.shields.io/github/license/Aleks130699/ha-fpp?style=for-the-badge)](LICENSE)

# HomeAssistant - Falcon Pi Player (FPP) Component

This is a custom component to allow control of the Falcon Pi Player in [Home Assistant](https://home-assistant.io). 

# Features:

* View current playing sequence and playlist
* Cover art support
* List all available playlist and sequences as sources
* Start a playlist or sequence
* Stop a playlist or sequence
* Set or step the player volume
* Next a sequence
* Prev a sequence
* Pause a sequence
* Resume a sequence
* Brightness Control (A plugin is required Brightness Control Plugin for FPP)

# Installation

### 1. Easy Mode

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Aleks130699&repository=ha-fpp&category=integration)
Install via HACS.


### 2. Manual

Install it as any custom homeassistant component:

1. Download `custom_components` folder.
2. Copy the `falcon_pi_player` directory to the `custom_components` directory of your homeassistant installation. Your `custom_components` directory resides within your homeassistant configuration directory.

**Note**: If the `custom_components` directory does not exist, you need to create it.

After a correct installation, your configuration directory should look like the following:

    
    └── ...
    └── configuration.yaml
    └── custom_components
        └── falcon_pi_player
            └── translations
                └── en.json
            └── __init__.py
            └── config_flow.py
            └── const.py
            └── light.py
            └── manifest.json
            └── media_player.py
            └── quality_scale.yaml
            └── strings.json

            
# Configuration

1. Add configuration via the user interface Falcon Pi Player
1.1 (Irrelevant alternative) Enable the component by editing your configuration.yaml file (within the config directory as well). Edit it by adding the following lines:
    ```
    # Example configuration.yaml entry
    media_player:
      - platform: falcon_pi_player
        name: FPP_NAME
        host: IP_ADDRESS 
        #port: PORT #optional
        #username: USERNAME #optional
        #password: PASSWORD #optional

2. Reboot Home Assistant
3. You're good to go!

# Album covers

To use the covers, you need to add jpg images to the image item on the fpp player through the File Manager, the file name must exactly match the file being played, replacing the extension. ".fseq", ".mp3" or ".mp4" to ".jpg"
