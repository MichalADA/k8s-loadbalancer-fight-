#!/usr/bin/env python3
import subprocess
import time
import random
import logging
import argparse
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger('k8s-battle')

def run_command(cmd, shell=False):
    """Run a command and return the output, with error handling."""
    try:
        if shell:
            result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
        else:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed: {e}")
        logger.debug(f"Error output: {e.stderr}")
        return None

def get_controllers(namespace):
    """Fetch all controllers (Deployments, StatefulSets, etc.) in the namespace."""
    logger.info(f"Getting controllers in namespace: {namespace}")
    
    # Check if namespace exists
    ns_check = run_command(["kubectl", "get", "namespace", namespace, "--no-headers", "--request-timeout=5s"])
    if not ns_check:
        logger.error(f"Namespace {namespace} does not exist!")
        return []
    
    # Try to get deployments first
    deployments = run_command([
        "kubectl", "get", "deployments", "-n", namespace, 
        "-o", "jsonpath='{range .items[*]}{.metadata.name}{\"\\n\"}{end}'",
        "--request-timeout=5s"
    ]) or ""
    
    # Try to get statefulsets
    statefulsets = run_command([
        "kubectl", "get", "statefulsets", "-n", namespace, 
        "-o", "jsonpath='{range .items[*]}{.metadata.name}{\"\\n\"}{end}'",
        "--request-timeout=5s"
    ]) or ""
    
    # Try to get replicasets
    replicasets = run_command([
        "kubectl", "get", "replicasets", "-n", namespace, 
        "-o", "jsonpath='{range .items[*]}{.metadata.name}{\"\\n\"}{end}'",
        "--request-timeout=5s"
    ]) or ""
    
    # Combine all controllers
    controllers = []
    for output in [deployments, statefulsets, replicasets]:
        if output:
            controllers.extend(output.replace("'", "").split("\n"))
    
    if not controllers:
        logger.warning("No controllers found in namespace")
        
    # Also get pod information for reporting
    pods_output = run_command([
        "kubectl", "get", "pods", "-n", namespace, 
        "-o", "jsonpath='{range .items[*]}{.metadata.name}{\"\\n\"}{end}'",
        "--request-timeout=5s"
    ]) or ""
    
    pods = pods_output.replace("'", "").split("\n")
    pods = [pod for pod in pods if pod]
    
    logger.info(f"Found {len(pods)} pods controlled by {len(controllers)} controllers")
    
    # Return tuple of (controllers, pods)
    return controllers, pods

def get_pod_metrics(pod_name, namespace):
    """Get CPU and memory usage for a pod."""
    metrics = {}
    
    # Try to get pod metrics
    try:
        cpu_cmd = f"kubectl top pod {pod_name} -n {namespace} --no-headers | awk '{{print $2}}'"
        mem_cmd = f"kubectl top pod {pod_name} -n {namespace} --no-headers | awk '{{print $3}}'"
        
        metrics['cpu'] = run_command(cpu_cmd, shell=True)
        metrics['memory'] = run_command(mem_cmd, shell=True)
        
        # Get restart count
        restart_cmd = f"kubectl get pod {pod_name} -n {namespace} -o jsonpath='{{.status.containerStatuses[0].restartCount}}'"
        metrics['restarts'] = run_command(restart_cmd, shell=True) or "0"
        
        # Get pod age
        age_cmd = f"kubectl get pod {pod_name} -n {namespace} -o jsonpath='{{.metadata.creationTimestamp}}'"
        creation_time = run_command(age_cmd, shell=True)
        if creation_time:
            creation_dt = datetime.strptime(creation_time, "%Y-%m-%dT%H:%M:%SZ")
            metrics['age'] = (datetime.utcnow() - creation_dt).total_seconds()
        
        return metrics
    except Exception as e:
        logger.warning(f"Error getting metrics for {pod_name}: {e}")
        return metrics

def select_controller_for_reduction(controllers, namespace, strategy='random'):
    """Select which controller to reduce based on the chosen strategy."""
    if not controllers:
        return None, None
        
    if strategy == 'random':
        controller = random.choice(controllers)
    else:
        # For now, just use random for all strategies
        # Could be extended to use controller-specific metrics
        controller = random.choice(controllers)
    
    # Determine controller type
    if run_command(f"kubectl get deployment {controller} -n {namespace}", shell=True):
        controller_type = "deployment"
    elif run_command(f"kubectl get statefulset {controller} -n {namespace}", shell=True):
        controller_type = "statefulset"
    else:
        controller_type = "replicaset"
        
    return controller, controller_type

def reduce_controller(controller_name, namespace, controller_type="deployment"):
    """Reduce the replicas of a controller by 1."""
    if not controller_name:
        return False
    
    # Get current replica count
    if controller_type == "deployment":
        replicas_cmd = f"kubectl get deployment {controller_name} -n {namespace} -o jsonpath='{{.spec.replicas}}'"
    elif controller_type == "statefulset":
        replicas_cmd = f"kubectl get statefulset {controller_name} -n {namespace} -o jsonpath='{{.spec.replicas}}'"
    else:  # replicaset
        replicas_cmd = f"kubectl get replicaset {controller_name} -n {namespace} -o jsonpath='{{.spec.replicas}}'"
        
    replicas = run_command(replicas_cmd, shell=True)
    
    if not replicas or not replicas.isdigit() or int(replicas) <= 0:
        logger.warning(f"Could not get replica count for {controller_type} {controller_name} or it's already at 0")
        return False
        
    new_replicas = max(0, int(replicas) - 1)
    logger.info(f"🔥 Reducing {controller_type} {controller_name} from {replicas} to {new_replicas} replicas 🔥")
    
    # Scale down the controller
    if controller_type == "deployment":
        result = run_command(["kubectl", "scale", "deployment", controller_name, 
                              "--replicas", str(new_replicas), "-n", namespace])
    elif controller_type == "statefulset":
        result = run_command(["kubectl", "scale", "statefulset", controller_name, 
                              "--replicas", str(new_replicas), "-n", namespace])
    else:  # replicaset
        result = run_command(["kubectl", "scale", "replicaset", controller_name, 
                              "--replicas", str(new_replicas), "-n", namespace])
    
    return result is not None

def battle(namespace, interval=10, strategy='random', max_rounds=None):
    """Run the controller battle."""
    logger.info(f"⚔️ Starting the battle in namespace: {namespace} ⚔️")
    logger.info(f"Strategy: {strategy}, Interval: {interval}s")
    
    round_num = 1
    
    while True:
        logger.info(f"\n=== ROUND {round_num} ===")
        
        # Get current controllers and pods
        controllers, pods = get_controllers(namespace)
        
        if not controllers:
            logger.info("🏆 No controllers found. The battle is over! 🏆")
            break
            
        if not pods:
            logger.info("🏆 No pods found. The battle is over! 🏆")
            break
        
        logger.info(f"Remaining controllers: {len(controllers)}")
        logger.info(f"Current pods: {len(pods)}")
        for pod in pods:
            metrics = get_pod_metrics(pod, namespace)
            metrics_str = ", ".join([f"{k}: {v}" for k, v in metrics.items() if v])
            logger.info(f"  - {pod} ({metrics_str})")
        
        if len(controllers) == 1 and len(pods) <= 1:
            if pods:
                logger.info(f"🏆 Winner: {pods[0]} 🏆")
            else:
                logger.info(f"🏆 Winner: {controllers[0]} (no running pods) 🏆")
            break
        
        # Select and reduce a controller
        target_controller, controller_type = select_controller_for_reduction(controllers, namespace, strategy)
        if target_controller:
            reduce_controller(target_controller, namespace, controller_type)
        
        # Check if max rounds reached
        if max_rounds and round_num >= max_rounds:
            logger.info(f"Maximum rounds ({max_rounds}) reached. Battle ended.")
            break
            
        round_num += 1
        
        logger.info(f"⏳ Next round in {interval} seconds...")
        time.sleep(interval)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Kubernetes Pod Battle Royale')
    parser.add_argument('--namespace', '-n', default="loadbalancer-fight", help='Kubernetes namespace to battle in')
    parser.add_argument('--interval', '-i', type=int, default=10, help='Interval between rounds in seconds')
    parser.add_argument('--strategy', '-s', choices=['random', 'youngest', 'oldest', 'resource-hog'], 
                        default='random', help='Pod elimination strategy')
    parser.add_argument('--max-rounds', '-m', type=int, default=None, help='Maximum number of rounds')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose logging')
    
    args = parser.parse_args()
    
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    try:
        battle(args.namespace, args.interval, args.strategy, args.max_rounds)
    except KeyboardInterrupt:
        logger.info("Battle stopped by user")
    except Exception as e:
        logger.error(f"Battle error: {e}")
