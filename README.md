
# Welcome to the Frontend Deployment of the Ghost App with CDK!

This is a project that aims to deploy infrastructure on AWS that will be hosting a Ghost application, as well as the application code.
Please note that this is the basis code for doing automated deployments, it can be enriched with much more features/services. It also represents my personal interpretation of the business case I was asked to complete during my interview with the company. I have chosen to use Elastic Container Service with Fargate Launch type for hosting the Ghost application, fronted by a Network Load Balancer. In the same repository I have also created a very basic buildspec file for building the application code, as well as a very small sample of application code. As mentioned above, this work is just a sample, and a detailed explanation of the architecture along with how it can be further developed are going to be given during the interview.

In order for the code to run, the different environments need to be prepared. This project follows an example of cross account deployment. This means that there are two different accounts on AWS, one that hosts the source code (in CodeCommit), both for the infrastructure provisioning as well as the application code and one, which will be the target account, in this case the Development account in which the architecture will be deployed, the resources will be created accordingly that will host the application, as well as the application code. Furthermore, it is assumed that the accounts are already set up, which means that fundamental resources e.g. VPCs, Security groups, Availability Zones, IPs are already in place.

It is also necessary to have a AWS CLI configured with the credentials of the target account (in our case, the Dev environment), since everything will be deployed there.

There is though some manual work that needs to be done. A role in the host account that will be assumed by the target account, with allowing access to CodeCommit service will be necessary. Also, two S3 buckets in the target account, one for storing the buildspec file, which will be necessary during the build of the application, and one for storing the artifacts of the CodePipeline, need to be created manually. The bucket name and key need to be encrypted and stored in KMS and need to be retrieved during the deployment phase. Please find the naming convention that is being followed inside the ` fe_build_deploy.py `. 
Furthermore, for encrypted traffic between the client and the Network Load Balancer a certificate needs to be uploaded to ACM and the ARN needs to be inserted into config.yaml. Last but not least, a repository in the Elastic Container Registry needs to be set up in the target account, from where the docker image will be pulled during the build. The reason why Dockerhub is not directly used, is because the times an image can be pulled from a registry are limited. Instructions are provided later on how to upload a Docker image on ECR.

## Folder Structure

Navigate to the folder
```
cd ghost_app_cdk/infra_cdk_code
```
1. `app.py` Contains the deployment code for the different stacks.
2. `config.yaml` Contains all the parameters of the stack and needs to be updated accordingly. In there you will find all the useful information on how to add the account specific variables.
3. `requirements.txt` Contains the necessary requirements for the code to run.
4. `setup.py` This is where you can add additional dependencies.

Once you execute ``` cd infra_cdk_code ``` 

5. `infra_cdk_code_stack.py` Code for provisioning the infrastructure.
6. `fe_build_deploy.py` Code for building and deploying the app code with CodePipeline, CodeBuild, CodeDeploy.
7. `event_rules_service_account_stack.py` Code for creating the event rule, event bus and event pattern in order to trigger the pipeline in the target account.

The repo of the ghost application ` cd my-ghost-app`
Note: The code should be stored in a separate repo in CodeCommit and the repo name should be passed as a parameter inside config.yaml as it will be the source of the CodePipeline. The buildspec file should be stored in a S3 bucket, the name of which should also be given as a parameter inside config.yaml. For the sake of the demo, it only containes a Docker file which pulls the ghost image from ECR and exposes the port that ghost originally runs. Normally this repo will contain all the frontend code of the application.

## Repository creation in ECR

We need to download the Ghost base image locally and then push it to ECR

1. ``` docker pull ghost ```
2. ``` aws ecr get-login-password --region eu-central-1 | docker login --username AWS --password-stdin $ACCOUNT_ID.dkr.ecr.eu-central-1.amazonaws.com ```
3. ``` docker tag ghost:latest $REPOSITORY_URI:latest ```
4. ``` docker push $REPOSITORY_URI:latest ```

All the above commands are used in order to push the base ghost image to ECR and use it from there, instead of Docker Hub.

## Code Deployment

You need to install cdk in order to run the code.
```
python -m pip install aws-cdk-lib
```
Then, navigate to the folder that contains the `app.py`. This file will synthesize and deploy the different stacks.
```
cd ghost_app_cdk/infra_cdk_code/
```
```
cdk synth
```
```
cdk deploy --all
```





