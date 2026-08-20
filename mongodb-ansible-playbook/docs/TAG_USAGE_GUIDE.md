# MongoDB Ansible Role - Tag Usage Guide

## Simplified Tag Structure
### Full Deployment (Install + Configure + Replicate + Secure + Summary)
```bash
ansible-playbook -i inventory mongodb-playbook.yml --tags "install,config,replication,security,summary"
``` tags have been cleaned up and simplified. Here are the available tags:

### Core Tags

| Tag | Description | Usage |
|-----|-------------|-------|
| `install` | Package installation | `--tags "install"` |
| `config` | Configuration files and basic setup | `--tags "config"` |
| `replication` | Replica set configuration | `--tags "replication"` |
| `security` | Authentication and authorization | `--tags "security"` |
| `backup` | Backup configuration | `--tags "backup"` |
| `validation` | Verification and testing tasks | `--tags "validation"` |
| `maintenance` | Logrotate and maintenance tasks | `--tags "maintenance"` |
| `monitoring` | Monitoring setup | `--tags "monitoring"` |
| `notification` | Slack/notification tasks | `--tags "notification"` |
| `info` | Information and debug messages | `--tags "info"` |
| `summary` | Deployment summary and validation report | `--tags "summary"` |

### Environment Tags

| Tag | Description | Usage |
|-----|-------------|-------|
| `community` | Community MongoDB installation | `--tags "install,community"` |
| `percona` | Percona Server for MongoDB | `--tags "install,percona"` |

### Deployment Type Tags

| Tag | Description | Usage |
|-----|-------------|-------|
| `pss` | Primary + Secondary + Secondary setup | `--tags "replication,pss"` |
| `arbiter` | Primary + Secondary + Arbiter setup | `--tags "replication,arbiter"` |
| `psp` | Primary + Secondary + Percona setup | `--tags "replication,psp"` |
| `single-node` | Single node replica set | `--tags "replication,single-node"` |

## Common Usage Examples

### Complete Installation and Setup
```bash
ansible-playbook -i inventory mongodb-playbook.yml --tags "install,config,replication,security"
```

### Install Community MongoDB Only
```bash
ansible-playbook -i inventory mongodb-playbook.yml --tags "install,community"
```

### Configure PSS Replication
```bash
ansible-playbook -i inventory mongodb-playbook.yml --tags "replication,pss"
```

### Security Setup Only
```bash
ansible-playbook -i inventory mongodb-playbook.yml --tags "security"
```

### Backup Configuration
```bash
ansible-playbook -i inventory mongodb-playbook.yml --tags "backup"
```

### Validation and Testing
```bash
ansible-playbook -i inventory mongodb-playbook.yml --tags "validation"
```

### Full Deployment (Install + Configure + Replicate + Secure)
```bash
ansible-playbook -i inventory mongodb-playbook.yml --tags "install,config,replication,security,validation"
```

### Maintenance Tasks Only
```bash
ansible-playbook -i inventory mongodb-playbook.yml --tags "maintenance"
```

### Generate Summary Report Only
```bash
ansible-playbook -i inventory mongodb-playbook.yml --tags "summary"
```

### Using the Deployment Script
```bash
# Basic deployment with summary
./deploy-mongodb.sh

# Custom inventory and tags
./deploy-mongodb.sh inventory.production "install,config,summary"
```

## Tag Combination Benefits

- **Faster execution**: Run only what you need
- **Better troubleshooting**: Isolate specific components
- **Flexible deployment**: Mix and match based on requirements
- **Reduced complexity**: Clear, single-purpose tags

## Notes

- The `all` tag has been removed from individual tasks to prevent confusion
- Tags are now more focused and single-purpose
- Use multiple tags separated by commas for comprehensive operations
- Each tag represents a logical grouping of related tasks