# Dockerfile usage instructions

A Dockerfile is a script that contains all the instructions needed to build a Docker container image. Below are the steps to build and run a Docker container based on a Dockerfile.

1. Clone the repository containing the Dockerfile to your local machine.
2. Change into the directory containing the Dockerfile.
3. Run the following command to build the Docker image:

    ```bash
    docker build -t certbot-azuredns -f Dockerfile .
    ```

4. Once the image is built, you can run a Docker container based on the image using the following command:

    ```bash
    docker run -it --rm --name certbot-azure-dns \
            -v /etc/letsencrypt/:/etc/letsencrypt/ \
            certbot-azuredns \
            certbot certonly \
            --authenticator dns-azure \
            --preferred-challenges dns \
            --agree-tos \
            --email 'address@example.com' \
            --noninteractive \
            --dns-azure-config /etc/letsencrypt/clouddns/azure.ini \
            --domains example.com \
            --domains '*.example.com'
    ```

5. And the contents of the `azure.ini` is as per the service principal example with 400 permission.

    ```yaml
    dns_azure_sp_client_id = AAA...
    dns_azure_sp_client_secret = BBB...
    dns_azure_tenant_id = CCC...
    dns_azure_environment = "AzurePublicCloud"
    dns_azure_zone1 = example.com:/subscriptions/DDD.../resourceGroups/rg-dns001
    ```

## Docker Compose usage instructions

1. Clone the repository containing the Dockerfile to your local machine.
2. Change into the directory containing the Dockerfile.
3. Using the docker compose file below you can the workload

    ```dockerfile
    version: '3.7'
    services:
    certbot-azure-dns-1:
        build:
        context: .
        dockerfile: Dockerfile
        container_name: certbot-azure-dns-1
        command: 
        - certbot 
        - certonly
        - "--email=example@outlook.com"
        - "--authenticator=dns-azure"
        - "--preferred-challenges=dns"
        - "--agree-tos"
        - "--noninteractive" 
        - "--dns-azure-config=/secret/azure.ini"
        - "--domains=example.org"
        - "--domains=*.example.org"
        volumes:
        - "./letsencrypt:/etc/letsencrypt"
        - "./secret:/secret:ro"
    ```
4. And the contents of the `azure.ini` is as per the service principal example with 400 permission in the `./secret` local directory.

    ```yaml
    dns_azure_sp_client_id = AAA...
    dns_azure_sp_client_secret = BBB...
    dns_azure_tenant_id = CCC...
    dns_azure_environment = "AzurePublicCloud"
    dns_azure_zone1 = example.com:/subscriptions/DDD.../resourceGroups/rg-dns001
    ```
