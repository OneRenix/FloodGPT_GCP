# Deploying to Cloud Run

This guide provides step-by-step instructions on how to deploy the FloodGPT application to Google Cloud Run.

## Prerequisites

1.  **Google Cloud Project:** You need a Google Cloud project with billing enabled.
2.  **Enable APIs:** Make sure the Cloud Run API and Artifact Registry API are enabled for your project. You can do this from the Google Cloud Console.
3.  **Install Google Cloud CLI:** Download and install the [Google Cloud CLI](https://cloud.google.com/sdk/docs/install).
4.  **Install Docker:** Download and install [Docker Desktop](https://www.docker.com/products/docker-desktop).

## Deployment Steps

### 1. Configure Google Cloud CLI

First, you need to authenticate and configure the gcloud CLI.

```bash
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
```

Replace `YOUR_PROJECT_ID` with your actual Google Cloud project ID.

### 2. Create an Artifact Registry Repository

You need a place to store your Docker image. We will use Artifact Registry.

Create a repository named `floodgpt` in the `us-central1` region (or your preferred region).

```bash
gcloud artifacts repositories create floodgpt --repository-format=docker --location=us-central1 --description="FloodGPT Docker repository"
```

### 3. Configure Docker

Configure Docker to use the gcloud CLI for authentication with Artifact Registry.

```bash
gcloud auth configure-docker us-central1-docker.pkg.dev
```

### 4. Build the Docker Image

Build the Docker image of the application. We will tag it with the Artifact Registry path.

```bash
docker build -t us-central1-docker.pkg.dev/YOUR_PROJECT_ID/floodgpt/floodgpt-image:v1 .
```

Make sure to replace `us-central1` with the region of your Artifact Registry, and `YOUR_PROJECT_ID` with your project ID.

### 5. Push the Docker Image

Push the image to Artifact Registry.

```bash
docker push us-central1-docker.pkg.dev/YOUR_PROJECT_ID/floodgpt/floodgpt-image:v1
```

### 6. Deploy to Cloud Run

Deploy the container image to Cloud Run.

```bash
gcloud run deploy floodgpt-service --image us-central1-docker.pkg.dev/YOUR_PROJECT_ID/floodgpt/floodgpt-image:v1 --platform managed --region us-central1 --allow-unauthenticated
```

-   `--region us-central1`: Specifies the region where you want to deploy your service. This should be the same region as your Artifact Registry repository for better performance.
-   `--allow-unauthenticated`: This makes your service publicly accessible. If you want to restrict access, you can use other options.

After the deployment is complete, the command will output the URL of your service.

## Accessing your Deployed Application

Once deployed, you can access your application at the URL provided by the `gcloud run deploy` command.

---
*This is a basic deployment guide. For more advanced configurations, such as setting up a custom domain, managing secrets, or configuring continuous deployment, please refer to the [Cloud Run documentation](https://cloud.google.com/run/docs).*
