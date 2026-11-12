from fastapi import APIRouter, Depends

from carenote.alerts.rules import RuleSet, default_rules
from carenote.auth.deps import CurrentUser, current_user

router = APIRouter(prefix="/alerts", tags=["alerts"], dependencies=[Depends(current_user)])


@router.get("/rules")
def get_rules(_: CurrentUser) -> RuleSet:
    """The active threshold rules (read-only), e.g. to draw normal ranges on charts."""
    return default_rules()
