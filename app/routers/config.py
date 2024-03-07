from logging import getLogger
from re import sub
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field
from requests import get
from requests.exceptions import RequestException

from ..const import URL_WILLOW_CONFIG
from ..internal.command_endpoints.main import init_command_endpoint
from ..internal.was import (
    construct_url,
    get_config,
    get_multinet,
    get_nvs,
    get_tz_config,
    get_was_config,
    post_config,
    post_nvs,
    post_was,
)

## fetched from https://worker.heywillow.io/api/config?&type=config&default=true 
LOCAL_DEFAULT_CONFIG = {
    "aec": True,
    "audio_codec": "PCM",
    "audio_response_type": "TTS",
    "bss": False,
    "command_endpoint": "Home Assistant",
    "display_timeout": 10,
    "hass_host": "homeassistant.local",
    "hass_port": 8123,
    "hass_tls": False,
    "lcd_brightness": 500,
    "mic_gain": 14,
    "mqtt_auth_type": "userpw",
    "mqtt_host": "your.mqtt.host",
    "mqtt_password": "your_mqtt_password",
    "mqtt_port": 1883,
    "mqtt_tls": False,
    "mqtt_topic": "your_mqtt_topic",
    "mqtt_username": "your_mqtt_username",
    "multiwake": False,
    "ntp_config": "Host",
    "ntp_host": "pool.ntp.org",
    "openhab_token": "your_openhab_token",
    "openhab_url": "your_openhab_url",
    "record_buffer": 12,
    "rest_auth_header": "your_header",
    "rest_auth_pass": "your_password",
    "rest_auth_type": "None",
    "rest_auth_user": "your_username",
    "rest_url": "http://your_rest_url",
    "show_prereleases": False,
    "speaker_volume": 60,
    "speech_rec_mode": "WIS",
    "stream_timeout": 5,
    "timezone": "UTC+5",
    "timezone_continent_city": "America/Menominee",
    "vad_mode": 2,
    "vad_timeout": 300,
    "wake_confirmation": False,
    "wake_mode": "2CH_95",
    "wake_word": "alexa",
    "wis_tts_url": "https://infer.tovera.io/api/tts",
    "wis_url": "https://infer.tovera.io/api/willow"
}

log = getLogger("WAS")
router = APIRouter(prefix="/api")


class GetConfig(BaseModel):
    type: Literal['config', 'nvs', 'ha_url', 'ha_token', 'multinet', 'was', 'tz'] = Field(
        Query(..., description='Configuration type')
    )
    default: Optional[bool] = False


@router.get("/config")
async def api_get_config(config: GetConfig = Depends()):
    log.debug('API GET CONFIG: Request')
    # TZ is special
    if config.type == "tz":
        config = get_tz_config(refresh=config.default)
        return JSONResponse(content=config)

    # Otherwise handle other config types
    if config.default:
        try:
            default_config = get(f"{URL_WILLOW_CONFIG}?type={config.type}").json()
        except RequestException as e:
            log.error(f"Failed to fetch default config from heywillow: {e}")
            default_config = LOCAL_DEFAULT_CONFIG
        if isinstance(default_config, dict):
            return default_config
        else:
            raise HTTPException(status_code=400, detail="Invalid default config")

    if config.type == "nvs":
        nvs = get_nvs()
        return JSONResponse(content=nvs)
    elif config.type == "config":
        config = get_config()
        if "wis_tts_url_v2" in config:
            config["wis_tts_url"] = sub("[&?]text=", "", config["wis_tts_url_v2"])
            del config["wis_tts_url_v2"]
        return JSONResponse(content=config)
    elif config.type == "ha_token":
        config = get_config()
        return PlainTextResponse(config["hass_token"])
    elif config.type == "ha_url":
        config = get_config()
        url = construct_url(config["hass_host"], config["hass_port"], config["hass_tls"])
        return PlainTextResponse(url)
    elif config.type == "multinet":
        config = get_multinet()
        return JSONResponse(content=config)
    elif config.type == "was":
        config = get_was_config()
        return JSONResponse(content=config)


class PostConfig(BaseModel):
    type: Literal['config', 'nvs', 'was'] = Field(Query(..., description='Configuration type'))
    apply: bool = Field(Query(..., description='Apply configuration to device'))


@router.post("/config")
async def api_post_config(request: Request, config: PostConfig = Depends()):
    log.debug('API POST CONFIG: Request')
    if config.type == "config":
        await post_config(request, config.apply)
        init_command_endpoint(request.app)
    elif config.type == "nvs":
        await post_nvs(request, config.apply)
    elif config.type == "was":
        await post_was(request, config.apply)
