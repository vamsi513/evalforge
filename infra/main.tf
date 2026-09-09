terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# The instance lives in the account's default VPC / default subnet for its
# AZ - it was never given a dedicated one, so this codifies that rather than
# creating new networking.
data "aws_vpc" "default" {
  default = true
}

data "aws_subnet" "default_az1" {
  filter {
    name   = "default-for-az"
    values = ["true"]
  }

  filter {
    name   = "availability-zone"
    values = ["us-east-1a"]
  }

  vpc_id = data.aws_vpc.default.id
}

# Referenced by name only - Terraform does not create or hold the private
# key material for an existing key pair.
data "aws_key_pair" "resume_projects" {
  key_name = var.key_name
}

resource "aws_security_group" "resume_projects" {
  name        = "resume-projects-sg"
  description = "SSH restricted to my IP; app ports open for public demo URLs"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description = "SSH from my IP"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.my_ip_cidr]
  }

  ingress {
    description = "nginx reverse proxy"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "AgentIQ FastAPI"
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "EvalForge FastAPI"
    from_port   = 8001
    to_port     = 8001
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "IncidentMemoryAI FastAPI"
    from_port   = 8002
    to_port     = 8002
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "IncidentMemoryAI RAG app (app.main, LLM generation + citations)"
    from_port   = 8003
    to_port     = 8003
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "IncidentMemoryAI Streamlit UI"
    from_port   = 8501
    to_port     = 8501
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_instance" "resume_projects" {
  ami                    = var.ami_id
  instance_type          = var.instance_type
  subnet_id              = data.aws_subnet.default_az1.id
  vpc_security_group_ids = [aws_security_group.resume_projects.id]
  key_name               = data.aws_key_pair.resume_projects.key_name

  # Bootstrap script the instance actually launched with (installs and
  # enables Docker). It only runs once, at first boot - recorded here so
  # this matches the real instance, not to re-trigger it.
  user_data = <<-EOF
    #!/bin/bash
    dnf update -y
    dnf install -y docker
    systemctl enable docker
    systemctl start docker
    usermod -aG docker ec2-user
  EOF

  root_block_device {
    volume_size           = 20
    volume_type           = "gp3"
    encrypted             = false
    delete_on_termination = true
  }

  tags = {
    Name = "resume-projects-agentiq-incidentmem"
  }
}

resource "aws_eip" "resume_projects" {
  domain   = "vpc"
  instance = aws_instance.resume_projects.id
}
