# k8s-loadbalancer-fight-


# k8s-loadbalancer-fight ⚔️

## Overview
**k8s-loadbalancer-fight** is a fun and educational Kubernetes project that simulates a battle between multiple HTTP servers (pods). The Kubernetes load balancer distributes traffic among them, and the pod receiving the least traffic gets eliminated. The last pod standing is the winner! 🎯🔥

## How It Works
1. **Multiple HTTP pods** (e.g., 3-5) are deployed, each responding with a unique message.
2. A **Kubernetes Service (LoadBalancer)** distributes traffic among the pods.
3. A script monitors traffic and **randomly eliminates** the pod receiving the least traffic.
4. The process continues until only one pod remains – the ultimate survivor! 🏆

## Why This Project?
- Demonstrates **Kubernetes Service Load Balancing** in a fun way.
- Helps understand **traffic distribution and pod scaling**.
- Teaches **self-healing mechanisms in Kubernetes**.
- Completely **local**, works with **kind-kind**.

## Getting Started
### Prerequisites
- **Dexbox** 
- **Docker** installed and running
- **kind (Kubernetes in Docker)** installed
- **kubectl** configured

### Deployment Steps
1. **Create a kind cluster**:
   ```sh
   kind create cluster --name loadbalancer-fight
   ```
2. **Deploy the pods and service**:
   ```sh
   kubectl apply -f deployment.yaml
   ```
3. **Expose the service**:
   ```sh
   kubectl port-forward svc/loadbalancer-fight 8080:80
   ```
4. **Run the traffic monitor & elimination script**:
   ```sh
   python fight_script.py
   ```
5. Watch the pods fight until only one survives! 🏆

## Future Improvements
- Add real-time **dashboard** for visualizing eliminations.
- Introduce **webhooks** to announce eliminations dynamically.
- Add **weighted traffic distribution** for more controlled fights.

## License
This project is open-source under the **MIT License**.

