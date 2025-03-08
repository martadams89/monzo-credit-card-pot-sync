# Kubernetes Deployment Guide

This directory contains Kubernetes manifests for deploying Monzo Credit Card Pot Sync to a Kubernetes cluster.

## Prerequisites

- A Kubernetes cluster
- `kubectl` configured to communicate with your cluster
- Ingress controller (like NGINX Ingress) installed
- Cert-manager installed (optional, for TLS)

## Deployment Steps

1. Create the namespace:
   ```bash
   kubectl create namespace monzo-pot-sync
   ```

2. Create a Secret with your environment variables:
   ```bash
   # Update the secrets.yaml file with your base64 encoded values first
   kubectl apply -f secrets.yaml -n monzo-pot-sync
   ```

3. Create the Persistent Volume Claim:
   ```bash
   kubectl apply -f pvc.yaml -n monzo-pot-sync
   ```

4. Deploy the application:
   ```bash
   kubectl apply -f deployment.yaml -n monzo-pot-sync
   ```

5. Create the service:
   ```bash
   kubectl apply -f service.yaml -n monzo-pot-sync
   ```

6. Apply the network policy:
   ```bash
   kubectl apply -f networkpolicy.yaml -n monzo-pot-sync
   ```

7. Set up horizontal pod autoscaling:
   ```bash
   kubectl apply -f hpa.yaml -n monzo-pot-sync
   ```

8. Configure the ingress:
   ```bash
   # Update the ingress.yaml with your domain name
   kubectl apply -f ingress.yaml -n monzo-pot-sync
   ```

## Verification

Check if the deployment is running:
```bash
kubectl get deployment -n monzo-pot-sync
kubectl get pods -n monzo-pot-sync
kubectl get svc -n monzo-pot-sync
kubectl get ingress -n monzo-pot-sync
```

Check the application logs:
```bash
kubectl logs -l app=monzo-pot-sync -n monzo-pot-sync
```

## Scaling

The application is configured with Horizontal Pod Autoscaler (HPA) which will automatically scale the number of pods based on CPU and memory usage. You can manually scale the deployment if needed:

```bash
kubectl scale deployment monzo-pot-sync -n monzo-pot-sync --replicas=3
```

## Updating

To update to a new version of the application:

```bash
kubectl set image deployment/monzo-pot-sync monzo-pot-sync=ghcr.io/martadams89/monzo-credit-card-pot-sync:new-tag -n monzo-pot-sync
```

## Cleanup

To delete all resources:

```bash
kubectl delete namespace monzo-pot-sync
```
