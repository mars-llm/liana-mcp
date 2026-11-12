"""Bounded, generated regtest wallet policies."""

from pydantic import BaseModel, ConfigDict, Field, model_validator


class WalletPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    primary_keys: int = Field(ge=2, le=8)
    primary_signatures: int = Field(ge=1, le=8)
    recovery_signer: int = Field(ge=1, le=8, description="One-based test signer number.")
    recovery_blocks: int = Field(ge=1, le=144)

    @model_validator(mode="after")
    def check_signers(self):
        if max(self.primary_signatures, self.recovery_signer) > self.primary_keys:
            raise ValueError("Threshold and recovery signer must fit the signer count.")
        return self


WORKSHOP_POLICY = WalletPolicy(
    primary_keys=5, primary_signatures=3, recovery_signer=3, recovery_blocks=6
)
