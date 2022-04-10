#!/usr/bin/env python3
from ruamel.yaml import YAML
from aws_cdk import (
    App, Tags
)

from infra_cdk_code.infra_cdk_code_stack import InfraCdkCodeStack
from infra_cdk_code.fe_build_deploy import FeBuildDeploy
from infra_cdk_code.event_rules_service_account_stack import EventRulesServiceAccountStack

def load_config() -> dict:
    """
    Import settings from YAML config
    :return: dict with configuration items
    """
    config_path = "./config.yaml"  
    if not config_path:
        raise RuntimeError("You need to specify config path")
    with open(config_path) as config_file:
        config = YAML().load(config_file.read())
    return config


def init_app() -> App:
    """
    Initiates CDK main_app for deployment
    :return: main_app
    """
    main_app = App()
    config = load_config()
    configd = {}

    # Deploy the same stack for all apps in the config-app.yaml
    for key, value in config['aws_vars'].items():
        configd['acc']=value
        for key, value in config['frontend-ghost-app'].items():
            configd['fe']=value

            deploy1 = InfraCdkCodeStack(
                        main_app,
                        f"cdk-fe-ghost-app-infra-pipeline-{configd['acc']['project']['shortName']}-{configd['acc']['accountId']}",
                        env={
                                'account': configd['acc']['accountId'],
                                'region': configd['acc']['region']
                            },
                        config=configd
                    )
            for key, value in configd['acc']['stack_tags'].items():
                Tags.of(main_app).add(key=key, value=value)
            
            deploy2 = FeBuildDeploy(
                        main_app,
                        f"cdk-ghost-app-deployment-pipeline-{configd['acc']['project']['shortName']}-{configd['acc']['accountId']}",
                        env={
                                'account': configd['acc']['accountId'],
                                'region': configd['acc']['region']
                            },
                        config=configd
                    )
            for key, value in configd['acc']['stack_tags'].items():
                Tags.of(main_app).add(key=key, value=value)
            
            deploy3 = EventRulesServiceAccountStack(
                main_app,
                f"cdk-event-rule-{configd['fe']['code']['name']}-infra-{configd['acc']['project']['shortName']}-{configd['acc']['service_account']['accountId']}",
                        env={
                            'account': configd['acc']['service_account']['accountId'],
                            'region': configd['acc']['service_account']['region']
                        },
                        config=configd
                )
            for key, value in configd['acc']['stack_tags'].items():
                Tags.of(main_app).add(key=key, value=value)

    return main_app

if __name__ == '__main__':
    app = init_app()
    app.synth()
