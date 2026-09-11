from pydantic import BaseModel, Field
class RuleUpdate(BaseModel):
    enabled: bool|None=None
    undercut_amount: float|None=Field(default=None,ge=0,le=1000000)
    auto_stop: bool|None=None
    auto_resume: bool|None=None
