# MongoDB Deployment Example

## Sample Inventory for PSS (Primary-Secondary-Secondary) Setup

```ini
# /home/user/mongodb-deployment/inventory.production

# Host definitions with connection details
primary ansible_host=172.20.212.38 ansible_user=ubuntu ansible_port=22 ansible_ssh_private_key_file=/path/to/key.pem
secondary ansible_host=172.20.212.71 ansible_user=ubuntu ansible_port=22 ansible_ssh_private_key_file=/path/to/key.pem  
secondary2 ansible_host=172.20.212.164 ansible_user=ubuntu ansible_port=22 ansible_ssh_private_key_file=/path/to/key.pem

# Group definitions (REQUIRED for the role to work properly)
[primary]
primary

[secondary]
secondary

[secondary2]
secondary2

# Combined group for all MongoDB nodes
[mongodb-pss]
primary
secondary
secondary2

# Global variables for all MongoDB hosts
[mongodb-pss:vars]
ansible_python_interpreter=/usr/bin/python3
ansible_become=yes
```

## Sample Deployment Commands

```bash
# 1. Complete deployment with summary
./deploy-mongodb.sh inventory.production

# 2. Step-by-step deployment
ansible-playbook -i inventory.production mongodb-playbook.yml --tags "install"
ansible-playbook -i inventory.production mongodb-playbook.yml --tags "config"  
ansible-playbook -i inventory.production mongodb-playbook.yml --tags "replication,pss"
ansible-playbook -i inventory.production mongodb-playbook.yml --tags "security"
ansible-playbook -i inventory.production mongodb-playbook.yml --tags "summary"

# 3. Generate summary report only
ansible-playbook -i inventory.production mongodb-playbook.yml --tags "summary"
```

## Expected Output Example

### During Deployment
```
TASK [mongodb : Setting up admin user password] ****************************
changed: [primary]

TASK [mongodb : Setting up Replication of primary and two secondary's] *****
changed: [primary]

TASK [mongodb : Display comprehensive deployment summary] *******************
ok: [primary] => {
    "msg": [
        "",
        "==========================================",
        "🍃 MONGODB DEPLOYMENT SUMMARY REPORT 🍃", 
        "==========================================",
        "",
        "📋 BASIC INFORMATION",
        "├─ Hostname: primary",
        "├─ IP Address: 172.20.212.38", 
        "├─ Operating System: Debian Ubuntu 20.04",
        "└─ Deployment Time: 2025-10-09T10:30:00Z",
        "",
        "📦 INSTALLATION DETAILS",
        "├─ MongoDB Type: Community MongoDB",
        "├─ Version: 6.0", 
        "├─ Service Status: active",
        "└─ Configuration File: /etc/mongod.conf",
        "",
        "🔄 REPLICATION SETUP", 
        "├─ Configuration: Primary-Secondary-Secondary (PSS)",
        "├─ Replica Set Name: rs0",
        "├─ Node Role: Primary",
        "└─ Priority: 2",
        "",
        "🔐 SECURITY CONFIGURATION",
        "├─ Authentication: ✅ Enabled",
        "├─ Authorization: ✅ Enabled", 
        "├─ Admin User: ✅ Created",
        "└─ Keyfile Auth: ✅ Enabled",
        "",
        "🔍 VALIDATION RESULTS",
        "├─ Binary Exists: ✅ Yes",
        "├─ Service Running: ✅ Active", 
        "├─ Connection Test: ✅ Success",
        "├─ Recent Errors: 0 found in logs",
        "└─ Overall Health: ✅ Healthy",
        "",
        "==========================================",
        "✅ DEPLOYMENT COMPLETED SUCCESSFULLY!",
        "=========================================="
    ]
}
```

### Cluster Overview (shown once)
```
TASK [mongodb : Display cluster overview (run once)] ***********************
ok: [primary] => {
    "msg": [
        "",
        "🏗️  MONGODB CLUSTER OVERVIEW",
        "====================================",
        "",  
        "Cluster Members:",
        "├─ primary (172.20.212.38) - Primary",
        "├─ secondary (172.20.212.71) - Secondary", 
        "└─ secondary2 (172.20.212.164) - Secondary2",
        "",
        "🔗 Connection Commands:",
        "├─ Direct Connection: mongo 172.20.212.38:27017",
        "├─ Replica Set Connection: mongo \"mongodb://primary:27017/admin?replicaSet=rs0\"",
        "└─ Authenticated Connection: mongo \"mongodb://admin:PASSWORD@172.20.212.38:27017/admin\"",
        "",
        "📝 Next Steps:",
        "├─ Verify cluster status: rs.status()",
        "├─ Check replica set config: rs.conf()", 
        "├─ Monitor logs: tail -f /var/log/mongodb/mongod.log",
        "└─ Test authentication: db.runCommand({connectionStatus: 1})",
        "",
        "====================================",
    ]
}
```

## Files Created During Deployment

### On Each Host:
- `/tmp/mongodb_deployment_summary_<hostname>_<timestamp>.txt` - Detailed text summary
- `/etc/mongod.conf` - MongoDB configuration 
- `/etc/logrotate.d/mongodb.conf` - Log rotation configuration
- `/opt/mongodb-venv/` - Python virtual environment for MongoDB modules

### Validation Commands Post-Deployment:

```bash
# Check service status
systemctl status mongod

# Test connection  
mongo <host>:27017

# Check replica set status
mongo --eval "rs.status()"

# Test authentication
mongo -u admin -p <password> --authenticationDatabase admin --eval "db.runCommand({connectionStatus: 1})"
```