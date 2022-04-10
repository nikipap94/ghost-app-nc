from aws_cdk import (
    Stack,  
    aws_events as events,
    aws_events_targets
)

from constructs import Construct
class EventRulesServiceAccountStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        config = kwargs.pop("config")
        super().__init__(scope, construct_id, **kwargs)


        cfg_account_id = config['acc']['accountId']
        cfg_region = config['acc']['region']

        cfg_service_account_id = config['acc']['service_account']['accountId']
        cfg_repo = config['fe']['code']['sourceRepo']
        cfg_branch = config['fe']['code']['sourceBranch']


           
        event_pattern = events.EventPattern(
                account=[cfg_service_account_id],
                source=["aws.codecommit"],
                resources=[f"arn:aws:codecommit:{cfg_region}:{cfg_service_account_id}:{cfg_repo}"],
                detail_type=["CodeCommit Repository State Change"],
                detail={
                    "referenceType": [
                      "branch"
                    ],
                    "event": [
                      "referenceCreated",
                      "referenceUpdated"
                    ],
                    "referenceName": [
                      cfg_branch
                    ]
                } 
            )

        target = aws_events_targets.EventBus(
              event_bus = events.EventBus.from_event_bus_arn(
                self, "event-bus-dst",
                event_bus_arn=f"arn:aws:events:{cfg_region}:{cfg_account_id}:event-bus/default" #ARN of the bus in the Hosting accoung
              )
        )

        event_rule = events.Rule(
            self, "event-rule",
            description=f"Trigger pipeline in the account {cfg_account_id} for the repository {cfg_repo}",
            enabled=True,
            event_pattern=event_pattern,
            targets=[target]
        )