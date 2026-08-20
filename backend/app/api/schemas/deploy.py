from pydantic import BaseModel, Field


class DeployRequest(BaseModel):
    tags: list[str] = Field(
        default=["install", "config", "replication", "security", "summary"],
        description="Ansible playbook tags to run",
    )


class RerunRequest(BaseModel):
    tags: list[str] = Field(min_length=1, description="At least one tag required")
