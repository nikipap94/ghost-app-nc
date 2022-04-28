from aws_cdk import (
    Stack, RemovalPolicy, Duration, CfnOutput,
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_iam as iam,
    aws_logs as logs,
    aws_elasticloadbalancingv2 as elbv2,
    Duration as Duration
)
from constructs import Construct

class CdkCodeStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        config = kwargs.pop("config")
        super().__init__(scope, construct_id, **kwargs)


        cfg_account_id = config['acc']['accountId']
        cfg_vpcid = config['acc']['resources']['vpcId']

        cfg_fe_name = config['fe']['code']['name']
        
        cfg_fe_td_cpu = config['fe']['ecs']['td_cpu']
        cfg_fe_td_mem = config['fe']['ecs']['td_memory']
        cfg_fe_con_cpu = config['fe']['ecs']['container_cpu']
        cfg_fe_con_mem = config['fe']['ecs']['container_memory']
        cfg_fe_con_port = config['fe']['ecs']['container_port']
        cfg_fe_host_port = config['fe']['ecs']['host_port']
        cfg_ecs_cluster_name = config['fe']['ecs']['cluster_name']

        cfg_fe_target_port = config['fe']['lb']['targer_port']
        cfg_fe_listener_certificate_arn = config['fe']['lb']['certificate_arn']

        vpc = ec2.Vpc.from_lookup(
            self, "vpc",
            vpc_id=cfg_vpcid,
            is_default=False
        )

        fs_security_group = ec2.SecurityGroup(
            self, "fssg",
            allow_all_outbound=True,
            vpc=vpc
        )

        fs_security_group.add_ingress_rule(
            ec2.Peer.any_ipv4(),
            ec2.Port.tcp(cfg_fe_con_port),
            f"SG for {cfg_fe_name} container in ECS"
        )

        cluster = ecs.Cluster.from_cluster_attributes(
            self, "ecscluster",
            cluster_name = cfg_ecs_cluster_name,
            vpc=vpc,
            security_groups=[fs_security_group]
        )

        ecsExecutionRole = iam.Role.from_role_arn(
                self, "executionrole",
                role_arn=f"arn:aws:iam::{cfg_account_id}:role/ecsTaskExecutionRole"
                )

        task_definition = ecs.TaskDefinition(
            self, "td",
            compatibility=ecs.Compatibility.FARGATE,
            family=f"{cfg_fe_name}",
            network_mode=ecs.NetworkMode.AWS_VPC,
            cpu=f"{cfg_fe_td_cpu}",
            memory_mib=f"{cfg_fe_td_mem}",
            execution_role=ecsExecutionRole,
            task_role=ecsExecutionRole         
        )

        container_log_driver = ecs.LogDriver.aws_logs(
            stream_prefix="ecs",
            log_group=logs.LogGroup(
                self, "loggroup",
            )
        )


        task_definition.add_container(
            f"{cfg_fe_name}-container",
            image=ecs.ContainerImage.from_registry("amazon/amazon-ecs-sample"), # default image
            cpu=cfg_fe_con_cpu,
            memory_limit_mib=cfg_fe_con_mem,
            logging=container_log_driver
        ).add_port_mappings(ecs.PortMapping(container_port=cfg_fe_con_port, host_port=cfg_fe_host_port))



        fargate_service = ecs.FargateService(
           self, "fs",
           cluster=cluster,
           desired_count=0,
           assign_public_ip=True,
           vpc_subnets=ec2.SubnetSelection(
               availability_zones=["eu-central-1c","eu-central-1b","eu-central-1a"]
            ),
            task_definition=task_definition,
            security_groups=[fs_security_group]
        )

        config['ecs_service_name'] = fargate_service.service_name


        load_balancer = elbv2.NetworkLoadBalancer(
           self,"network-load-balancer", 
           vpc=vpc,
           vpc_subnets=ec2.SubnetSelection(
               availability_zones=["eu-central-1c","eu-central-1b","eu-central-1a"]
           )
        )

        certificate = elbv2.ListenerCertificate.from_arn(
            certificate_arn=cfg_fe_listener_certificate_arn
        )

        tls_listener = elbv2.NetworkListener(
            self, "tlsListener",
            load_balancer=load_balancer,
            certificates=[certificate],
            port=cfg_fe_target_port
        )


        tls_listener.add_targets(
            "ECS1",
            port=cfg_fe_host_port,
            targets=[fargate_service],
            protocol=elbv2.Protocol.TCP,
            deregistration_delay=Duration.seconds(60)
        )
     
        # Output
           
        CfnOutput(
            self, "ecs_name",
            description="ecs cluster arn",
            value=cluster.cluster_arn
        )