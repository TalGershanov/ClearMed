#!/usr/bin/env bash
# Provisions a new EC2 instance for self-hosted OpenMRS (O3 Reference Application).
#
# Run this yourself with your own AWS credentials configured (`aws configure`).
# It creates: a security group (22 from your IP only, 80 + 443 from anywhere)
# and a t3.medium instance running Ubuntu 22.04.
#
# No Elastic IP is allocated — EIPs are billed once they're not associated
# with a running instance (e.g. while the instance is stopped), so this setup
# instead relies on DuckDNS: setup-host.sh installs a systemd timer on the
# instance that hits the DuckDNS update API on every boot (plus periodically
# as a safety net), keeping clearmed-openmrs.duckdns.org pointed at whatever
# public IP the instance currently has — no manual DNS step needed, and no
# EIP charges while the instance is stopped.
#
# Usage:
#   AWS_REGION=... KEY_NAME=... ./provision-instance.sh
#
# Prints the instance ID, security group ID, and its (dynamic) public IP at
# the end. Then run setup-host.sh on the instance over SSH — see
# infra/openmrs/README.md.

set -euo pipefail

# ---- Required/overridable settings ----
AWS_REGION="${AWS_REGION:-}"                 # e.g. eu-west-1 — same region as the existing ClearMed backend instance
KEY_NAME="${KEY_NAME:-}"                     # an existing EC2 key pair name in that region
ADMIN_CIDR="${ADMIN_CIDR:-}"                 # your IP for SSH access, e.g. 203.0.113.7/32 (curl ifconfig.me)
INSTANCE_TYPE="${INSTANCE_TYPE:-t3.medium}"
INSTANCE_NAME="${INSTANCE_NAME:-clearmed-openmrs}"
SG_NAME="${SG_NAME:-clearmed-openmrs-sg}"

if [[ -z "$AWS_REGION" || -z "$KEY_NAME" || -z "$ADMIN_CIDR" ]]; then
  echo "Set AWS_REGION, KEY_NAME, and ADMIN_CIDR (your IP as x.x.x.x/32) before running." >&2
  echo "Example: AWS_REGION=eu-west-1 KEY_NAME=clearmed ADMIN_CIDR=\$(curl -s ifconfig.me)/32 ./provision-instance.sh" >&2
  exit 1
fi

echo "== Looking up default VPC in $AWS_REGION =="
VPC_ID=$(aws ec2 describe-vpcs --region "$AWS_REGION" \
  --filters Name=isDefault,Values=true \
  --query 'Vpcs[0].VpcId' --output text)
if [[ "$VPC_ID" == "None" || -z "$VPC_ID" ]]; then
  echo "No default VPC found in $AWS_REGION — pass an existing VPC/subnet manually." >&2
  exit 1
fi
echo "VPC: $VPC_ID"

echo "== Creating security group =="
SG_ID=$(aws ec2 create-security-group --region "$AWS_REGION" \
  --group-name "$SG_NAME" \
  --description "ClearMed self-hosted OpenMRS: SSH from admin IP, HTTP/HTTPS from anywhere" \
  --vpc-id "$VPC_ID" \
  --query 'GroupId' --output text)
echo "Security group: $SG_ID"

aws ec2 authorize-security-group-ingress --region "$AWS_REGION" --group-id "$SG_ID" \
  --ip-permissions \
    "IpProtocol=tcp,FromPort=22,ToPort=22,IpRanges=[{CidrIp=$ADMIN_CIDR,Description=admin-ssh}]" \
    "IpProtocol=tcp,FromPort=80,ToPort=80,IpRanges=[{CidrIp=0.0.0.0/0,Description=http-acme-challenge}]" \
    "IpProtocol=tcp,FromPort=443,ToPort=443,IpRanges=[{CidrIp=0.0.0.0/0,Description=https}]" \
  >/dev/null

echo "== Looking up latest Ubuntu 22.04 LTS AMI =="
AMI_ID=$(aws ssm get-parameters --region "$AWS_REGION" \
  --names /aws/service/canonical/ubuntu/server/22.04/stable/current/amd64/hvm/ebs-gp2/ami-id \
  --query 'Parameters[0].Value' --output text)
echo "AMI: $AMI_ID"

echo "== Launching $INSTANCE_TYPE instance =="
INSTANCE_ID=$(aws ec2 run-instances --region "$AWS_REGION" \
  --image-id "$AMI_ID" \
  --instance-type "$INSTANCE_TYPE" \
  --key-name "$KEY_NAME" \
  --security-group-ids "$SG_ID" \
  --block-device-mappings 'DeviceName=/dev/sda1,Ebs={VolumeSize=30,VolumeType=gp3}' \
  --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$INSTANCE_NAME}]" \
  --query 'Instances[0].InstanceId' --output text)
echo "Instance: $INSTANCE_ID (waiting for it to be running...)"

aws ec2 wait instance-running --region "$AWS_REGION" --instance-ids "$INSTANCE_ID"

PUBLIC_IP=$(aws ec2 describe-instances --region "$AWS_REGION" \
  --instance-ids "$INSTANCE_ID" \
  --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)

cat <<EOF

== Done ==
Instance ID:      $INSTANCE_ID
Security group:   $SG_ID
Public IP (dynamic): $PUBLIC_IP

This IP is NOT static — it will change if the instance is ever stopped and
started again (a plain reboot keeps it). setup-host.sh installs a DuckDNS
auto-updater on the box so clearmed-openmrs.duckdns.org self-heals whenever
that happens; you don't need to update DNS by hand, now or later.

Next steps:
1. SSH in:  ssh -i <your-key>.pem ubuntu@$PUBLIC_IP
2. Copy infra/openmrs/setup-host.sh, .env.production, and duckdns.env onto
   the box and run setup-host.sh (see infra/openmrs/README.md).
EOF
