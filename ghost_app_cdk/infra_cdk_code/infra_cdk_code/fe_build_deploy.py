from aws_cdk import (
    Stack, CfnOutput, RemovalPolicy, RemovalPolicy,
    Duration,
    aws_s3 as s3,
    aws_ec2 as ec2,
    aws_ecr as _ecr,
    aws_ecs as ecs,
    aws_codebuild as codebuild,
    aws_codepipeline as codepipeline,
    aws_codepipeline_actions,
    aws_codecommit as codecommit,
    aws_ssm as ssm,
    aws_iam as iam,
    aws_kms as kms,
    aws_events as events,
    aws_events_targets,
)

from constructs import Construct

class FeBuildDeploy(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        config = kwargs.pop("config")
        super().__init__(scope, construct_id, **kwargs)

        cfg_account_id = config['acc']['accountId']
        cfg_region = config['acc']['region']
        cfg_vpcid = config['acc']['resources']['vpcId']
        cfg_env = config['acc']['env']
        cfg_project_short_name = config['acc']['project']['shortName']
        cfg_project_client = config['acc']['project']['client']
        cfg_service_account_id = config['acc']['service_account']['accountId']
        cfg_service_account_role = config['acc']['service_account']['crossAccountRole']
        cfg_app_name = config['fe']['code']['name']
        cfg_repo = config['fe']['code']['sourceRepo']
        cfg_branch = config['fe']['code']['sourceBranch']
        cfg_buildspec = config['fe']['code']['buildspec_path']
        cfg_ecs_service_name = config['ecs_service_name']
        cfg_ecs_cluster_name = config['fe']['ecs']['cluster_name']
        cfg_vc_con_port = config['fe']['ecs']['container_port']

        ecr = _ecr.Repository(
            self, "ecr",
            repository_name=f"{cfg_app_name}",
            removal_policy=RemovalPolicy.DESTROY
        )

        artifacts_bucket = s3.Bucket(
            self, "artifacts_bucket",
            bucket_name=f"{cfg_env}.fr-artifacts.{cfg_account_id}.{cfg_project_short_name}.{cfg_project_client}.s3",
            removal_policy=RemovalPolicy.RETAIN
        )

        vpc = ec2.Vpc.from_lookup(
            self, "vpc",
            vpc_id=cfg_vpcid,
            is_default=False
        )

        endpoint = ec2.InterfaceVpcEndpoint(
            self,
            "endpoint",
            vpc=vpc,
            service=ec2.InterfaceVpcEndpointAwsService(
                name="codepipeline"
            ),
            private_dns_enabled=False
        )

        buildproject = codebuild.PipelineProject(
            self, "buildproject",
            build_spec=codebuild.BuildSpec.from_source_filename(
                filename=cfg_buildspec),
            environment= codebuild.BuildEnvironment(
                build_image=codebuild.LinuxBuildImage.STANDARD_5_0,
                privileged=True,
                compute_type=codebuild.ComputeType.SMALL,
            ),

            environment_variables={
                'REPOSITORY_URI': codebuild.BuildEnvironmentVariable(
                    value=ecr.repository_uri),
                'BRANCH': codebuild.BuildEnvironmentVariable(
                    value=cfg_branch),
                'ACCOUNT_ID': codebuild.BuildEnvironmentVariable(
                    value=cfg_account_id),
                'ARTIFACTS_BUCKET': codebuild.BuildEnvironmentVariable(
                    value=artifacts_bucket.bucket_name
                ),
                'ECS_SERVICE_NAME': codebuild.BuildEnvironmentVariable(
                    value=cfg_ecs_service_name),
                'AWS_REGION': codebuild.BuildEnvironmentVariable(
                    value=cfg_region),
                'FAMILY': codebuild.BuildEnvironmentVariable(
                    value=f"{cfg_app_name}",),
            },
            description=f'Build docker image for {cfg_app_name}',
            vpc=vpc
        )

        ecr.grant_pull_push(buildproject)

        artifacts_bucket.grant_read_write(buildproject)

        buildproject.add_to_role_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "codecommit:GetBranch",
                "codecommit:GetCommit"
            ],
            resources=[f'arn:aws:codecommit:{cfg_region}:{cfg_service_account_id}:{cfg_repo}'],
            )
        )

        
        buildproject.add_to_role_policy(
                iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "ecr:BatchCheckLayerAvailability",
                    "ecr:GetDownloadUrlForLayer",
                    "ecr:BatchGetImage"
                ],
                resources=[] # Add the ARN of the ECR that hosts the ghost image,
                )
        )
        
        buildproject.add_to_role_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "s3:PutObject*",
                "s3:GetBucket*",
                "s3:GetObject*",
                "s3:ListBucket",
                "s3:DeleteObject"
            ],
            resources=[] # Add the ARN of the S3 bucket that the buildspec file is located
            )
        )



        buildproject.add_to_role_policy(
                iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "iam:CreateRole"
                ],
                resources=["*"],
                )
        )

        source_output = codepipeline.Artifact(artifact_name='source')

        build_output = codepipeline.Artifact(artifact_name='build')


        source = aws_codepipeline_actions.CodeCommitSourceAction(
            action_name="source",
            repository=codecommit.Repository.from_repository_name(
                self, "codebuildsourcerepo",
                repository_name=cfg_repo,
            ),
            branch=cfg_branch,
            output=source_output,
            role=iam.Role.from_role_arn(
                self, "addrole",
                role_arn=f'{cfg_service_account_role}') 
            )
        
        kms_arn = ssm.StringParameter.from_string_parameter_name(
            self, "kms_arn_string",
            string_parameter_name=f"{cfg_env}.crossaccount-artifacts-backet-key-{cfg_account_id}.{cfg_project_short_name}.secret"
        ) 
    
        bucket_name = ssm.StringParameter.from_string_parameter_name(
            self, "bucket_name_string",
            string_parameter_name=f"{cfg_env}.crossaccount-artifacts-backet-name-{cfg_account_id}.{cfg_project_short_name}.name",
        ) 

        bucket_key = kms.Key.from_key_arn(
            self, "artbucket_key",
            key_arn=kms_arn.string_value
        )

        cross_account_artifacts_bucket = s3.Bucket.from_bucket_attributes(
                self,  "artbucket",
                bucket_name=bucket_name.string_value,
                encryption_key=bucket_key
        )

        pipeline = codepipeline.Pipeline(
            self, f"pipeline-{cfg_app_name}",
            restart_execution_on_update=True,
            artifact_bucket=cross_account_artifacts_bucket
        )

        pipeline.add_to_role_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "kms:Decrypt",
                "kms:DescribeKey",
                "kms:Encrypt",
                "kms:ReEncrypt*",
                "kms:GenerateDataKey*"
            ],
            resources=[kms_arn.string_value],
            )
        )       

        pipeline.add_to_role_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "sts:AssumeRole"
            ],
            resources=[f'arn:aws:iam::{cfg_service_account_id}:role/*'],
            )
        )

        pipeline.add_stage(
            stage_name="source",
            actions=[source]
        )

        build_action = aws_codepipeline_actions.CodeBuildAction(
            action_name=f"build-image",
            project=buildproject,
            input=source_output,
            outputs=[build_output],
            variables_namespace="BuildVariables"
        )


        pipeline.add_stage(
            stage_name="build",
            actions=[build_action]
        )

        sg = ec2.SecurityGroup(
            self, "sgforcontainer",
            vpc=vpc,
            allow_all_outbound=True
        )        
        
        sg.add_ingress_rule(
            ec2.Peer.any_ipv4(),
            ec2.Port.tcp(cfg_vc_con_port),
            f"SG for {cfg_app_name} container in ECS"
        )

        deploy_action = aws_codepipeline_actions.EcsDeployAction(
            action_name=f"deploy-to-ecs",
            service=ecs.FargateService.from_fargate_service_attributes(
                            self, "fargateservicefromname",
                            service_name=cfg_ecs_service_name,
                            cluster=ecs.Cluster.from_cluster_attributes(
                                self, "ecsclusterfromname",
                                cluster_name=cfg_ecs_cluster_name,
                                vpc=vpc,
                                security_groups=[sg]
                            )
                    ),
            input=build_output,
            deployment_timeout=Duration.minutes(18)
        )


        pipeline.add_stage(
            stage_name="deploy",
            actions=[deploy_action]
        )


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

        target=aws_events_targets.CodePipeline(
                pipeline
                )

        event_rule = events.Rule(
            self, "eventrule",
            enabled=True,
            event_pattern=event_pattern,
            targets=[target]
        )


        
        # Output
           
        CfnOutput(
            self, "ecr_name",
            description="ECR Admin App name",
            value=ecr.repository_name
        )