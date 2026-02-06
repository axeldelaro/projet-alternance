from pydantic import BaseModel, ConfigDict
from datetime import datetime

class SensorDataResponse(BaseModel):
    timestamp: datetime
    temperature: float
    humidity: float
    model_config = ConfigDict(from_attributes=True)

class DeviceStatusResponse(BaseModel):
    device_name: str
    status: str
    timestamp: datetime
    model_config = ConfigDict(from_attributes=True)

# TODO: ajouter LogResponse
