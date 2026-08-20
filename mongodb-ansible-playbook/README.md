<!--
README.md Documentation Comment

This README provides comprehensive instructions for deploying a secure, production-ready MongoDB replica set using Ansible. It covers prerequisites, infrastructure setup, inventory and variable configuration, step-by-step deployment, troubleshooting, security features, monitoring integration, and post-deployment validation. The document also includes a detailed project structure, configuration options, and a checklist to ensure successful deployment. Contribution guidelines and support channels are outlined for users and collaborators.
-->
---
marp: false
---

# MongoDB Replica Set Deployment with Ansible

This repository contains Ansible playbooks and roles to deploy a production-ready MongoDB replica set with authentication, monitoring, and security configurations.

## 📋 Prerequisites

### System Requirements
- **Operating System**: Ubuntu 20.04+ or Debian 11+
- **RAM**: Minimum 4GB per node, recommended 8GB+
- **Storage**: Minimum 100GB external volume mounted at `/datadrive`
- **Network**: All nodes should be able to communicate on the MongoDB port (default: 37017)

### Required Software
- **Ansible**: Version 2.9+
- **Python**: Version 3.8+
- **SSH Access**: Passwordless SSH access to all target servers

### Infrastructure Setup
- **3 Servers**: Primary, Secondary, and Hidden nodes
- **External Volumes**: Each server should have an external volume (e.g., `/dev/nvme1n1`)
- **Network Security**: Ensure firewall rules allow MongoDB traffic between nodes

## 🚀 Quick Start

### 1. Clone and Setup

```bash
git clone <repository-url>
cd mongodb-ansible-deployment
```

### 2. Install Dependencies

```bash
# Install Ansible
sudo apt update
sudo apt install ansible python3-pip -y

# Install required Ansible collections
ansible-galaxy collection install community.mongodb
ansible-galaxy collection install community.general
```

### 3. Configure Inventory

Edit `inventory.production` with your server details:

```ini
[primary]
primary ansible_host=10.0.1.xx ansible_port=22 ansible_user=ubuntu ansible_ssh_private_key_file=/path/to/your/key.pem

[secondary] 
secondary ansible_host=10.0.1.xx ansible_port=22 ansible_user=ubuntu ansible_ssh_private_key_file=/path/to/your/key.pem

[hidden]
hidden ansible_host=10.0.1.xx ansible_port=22 ansible_user=ubuntu ansible_ssh_private_key_file=/path/to/your/key.pem

[mongodb:children]
primary
secondary
hidden

[mongodb:vars]
ansible_python_interpreter=/usr/bin/python3
ansible_become=true
ansible_become_method=sudo
```

### 4. Configure Variables

Edit the variables in `mongodb/vars/main.yml`:

```yaml
# Essential configurations
admin_password: "your_secure_password_here"
mongodb_port: 37017
mongodb_version: "8.0"


# Storage configuration
external_volume: "/dev/nvme1n1"
mount_path: "/datadrive"
dbPath: "/datadrive/mongodb/data/mongo"
logDir: "/datadrive/mongodb/logs"
```

### 5. Deploy MongoDB

Run the complete deployment:

```bash
Switch to Root User and install ansible on root
```

```bash
# Using the deployment script (recommended)
./deploy-mongodb.sh inventory.production

# Or run directly with ansible-playbook
ansible-playbook -i inventory.production mongodb-playbook.yml --tags "install,config,replication,security,summary"
```

## 📊 Deployment Summary Report

After deployment, you'll see a comprehensive summary report showing:

### 🔍 What Gets Reported
- **Installation Details**: MongoDB type, version, paths
- **Network Configuration**: Bind IP, ports, accessibility  
- **Replication Setup**: Replica set type, node roles, priorities
- **Security Status**: Authentication, authorization, SSL status
- **Backup Configuration**: Percona Backup Manager status
- **System Resources**: Disk usage, process information
- **Validation Results**: Health checks and connection tests

### 📄 Sample Summary Output
```
🍃 MONGODB DEPLOYMENT SUMMARY REPORT 🍃
==========================================

📋 BASIC INFORMATION
├─ Hostname: primary
├─ IP Address: 10.0.1.10
├─ Operating System: Debian Ubuntu 20.04
└─ Deployment Time: 2025-10-09T10:30:00Z

📦 INSTALLATION DETAILS  
├─ MongoDB Type: Community MongoDB
├─ Version: 6.0
├─ Service Status: active
└─ Overall Health: ✅ Healthy

🔄 REPLICATION SETUP
├─ Configuration: Primary-Secondary-Secondary (PSS)
├─ Node Role: Primary
└─ Replica Set Name: rs0

🔐 SECURITY CONFIGURATION
├─ Authentication: ✅ Enabled
├─ Authorization: ✅ Enabled
└─ Admin User: ✅ Created
```

### 📁 Summary Files
- Detailed summary saved to `/tmp/mongodb_deployment_summary_<hostname>_<timestamp>.txt` on each host
- Use `--tags "summary"` to generate report without running full deployment

## 📁 Project Structure

```
.
├── README.md
├── mongdb-playbook.yml           # Main playbook
├── inventory.production          # Inventory file
└── mongodb/                      # MongoDB role
    ├── defaults/
    │   └── main.yml             # Default variables
    ├── handlers/
    │   └── main.yml             # Service handlers
    ├── tasks/
    │   ├── main.yml             # Main task orchestration
    │   ├── Debian.yml           # OS-specific tasks
    │   ├── configure-mongodb.yml # MongoDB configuration
    │   ├── admin_user_creation.yml # Admin user setup
    │   ├── Replicaset.yml       # Replica set initialization
    │   ├── security.yml         # Security configurations
    │   ├── monitoring.yml       # Monitoring setup
    │   └── validation.yml       # Deployment validation
    ├── templates/
    │   ├── mongo-*.conf.j2      # MongoDB configuration templates
    │   └── *.service.j2         # Service templates
    └── vars/
        ├── main.yml             # Main variables
        ├── Debian.yml           # OS-specific variables
        └── environments/
            └── production.yml   # Environment-specific variables
```

## ⚙️ Configuration Options

### Essential Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `admin_password` | MongoDB admin password | - | ✅ |
| `mongodb_port` | MongoDB port | 37017 | ✅ |
| `primary` | Primary server IP | - | ✅ |
| `secondary` | Secondary server IP | - | ✅ |
| `hidden` | Hidden server IP | - | ✅ |
| `external_volume` | External volume path | /dev/nvme1n1 | ✅ |

### Optional Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `mongodb_version` | MongoDB version | 8.0 |
| `mount_path` | Mount point for data | /datadrive |
| `monitoring_password` | Monitoring user password | auto-generated |
| `slack_token` | Slack notification token | - |


## 🔧 Step-by-Step Deployment Process

The playbook follows this sequence:

### 1. **System Preparation**
- Install required packages and dependencies
- Create Python virtual environment with PyMongo 4+
- Setup external volume and filesystem

### 2. **MongoDB Installation**
- Add MongoDB repository and GPG keys
- Install MongoDB 8.0.11
- Configure initial settings

### 3. **Admin User Creation**
- Create admin user with full privileges
- Configure basic authentication

### 4. **Replica Set Initialization**
- Apply replication configuration (without keyFile)
- Initialize replica set without authentication
- Configure primary, secondary, and hidden nodes

### 5. **Security Enablement**
- Enable keyFile for inter-node authentication
- Apply authorization configuration
- Restart services with full security

### 6. **Validation and Testing**
- Verify replica set status
- Test authentication and authorization
- Run performance benchmarks

## 🛠️ Troubleshooting

### Common Issues

#### 1. PyMongo Version Error
**Error**: `You must use pymongo 4+`

**Solution**: The playbook automatically creates a virtual environment. If issues persist:
```bash
# Manually create virtual environment
sudo python3 -m venv /opt/mongodb-venv
sudo /opt/mongodb-venv/bin/pip install pymongo>=4.0 dnspython
```

#### 2. Authentication Errors During Replica Set Setup
**Error**: `Command replSetInitiate requires authentication`

**Solution**: This is handled automatically by the playbook sequence. Ensure you're running the complete playbook, not individual tasks.

#### 3. External Volume Not Found
**Error**: `External volume /dev/nvme1n1 does not exist`

**Solution**: 
```bash
# Check available disks
lsblk
# Update the external_volume variable in vars/main.yml
```

#### 4. MongoDB Service Fails to Start
**Solution**:
```bash
# Check service status
sudo systemctl status mongod

# Check logs
sudo journalctl -u mongod -f

# Check configuration
sudo mongod --config /etc/mongod.conf --configtest
```

### Debug Mode

Run with verbose output:
```bash
ansible-playbook -i inventory.production mongdb-playbook.yml -vvv
```

### Partial Deployment

Run specific parts:
```bash
# Install only
ansible-playbook -i inventory.production mongodb-playbook.yml --tags "install"

# Setup replication only
ansible-playbook -i inventory.production mongodb-playbook.yml --tags "replication"

# Configure security only
ansible-playbook -i inventory.production mongodb-playbook.yml --tags "security"

# Single node setup
ansible-playbook -i inventory.production mongodb-playbook.yml --tags "single-node"

# Percona-specific setup
ansible-playbook -i inventory.production mongodb-playbook.yml --tags "percona-setup"

# Community MongoDB setup
ansible-playbook -i inventory.production mongodb-playbook.yml --tags "community-setup"

# Backup setup only
ansible-playbook -i inventory.production mongodb-playbook.yml --tags "backup"

# Skip specific parts
ansible-playbook -i inventory.production mongodb-playbook.yml --skip-tags "backup,notification"


## 🔐 Security Features

- **Authentication**: Admin user with strong password
- **Authorization**: Role-based access control
- **Network Security**: Bind to specific interfaces only
- **Inter-node Security**: KeyFile authentication for replica set
- **JavaScript Disabled**: Server-side JavaScript disabled
- **Log Rotation**: Automated log management

## 📊 Monitoring Setup

The playbook includes optional monitoring setup:

- **MongoDB Exporter**: Prometheus metrics exporter
- **Health Checks**: Automated health monitoring scripts
- **Performance Profiling**: Slow operation tracking

To enable monitoring:
```bash
# Set monitoring variables in vars/main.yml
enable_monitoring: true
monitoring_password: "secure_monitoring_password"
```

```

## 📝 Post-Deployment

After successful deployment:

1. **Test Connection**:
```bash
mongosh "mongodb://admin:your_password@primary:37017/admin?replicaSet=rs0"
```

2. **Check Replica Set Status**:
```javascript
rs.status()
```

3. **Verify Authentication**:
```javascript
db.runCommand({listUsers: 1})
```

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request



## 🆘 Support

- **Documentation**: Check this README and code comments
- **Issues**: Create an issue in the repository
- **Security**: Report security issues privately

## 📋 Checklist

Before deployment, ensure:

- [ ] All servers are accessible via SSH
- [ ] External volumes are attached to all servers
- [ ] Firewall rules allow MongoDB traffic
- [ ] Inventory file is correctly configured
- [ ] Variables are set in `vars/main.yml`
- [ ] Ansible and required collections are installed

After deployment, verify:

- [ ] All MongoDB services are running
- [ ] Replica set is properly initialized
- [ ] Authentication works correctly
