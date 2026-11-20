"""Shared Pydantic base classes: strict input (extra fields rejected), ORM-friendly output."""

from pydantic import BaseModel, ConfigDict


class In(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)
