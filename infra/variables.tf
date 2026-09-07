variable "aws_region" {
  description = "AWS region the resume-projects host runs in"
  type        = string
  default     = "us-east-1"
}

variable "my_ip_cidr" {
  description = "CIDR allowed to SSH into the instance. Update this when your IP changes instead of editing the security group by hand."
  type        = string
  default     = "35.150.38.53/32"
}

variable "key_name" {
  description = "Name of the existing EC2 key pair. Terraform references it by name only - it does not create or manage the private key."
  type        = string
  default     = "resume-projects-key"
}

variable "instance_type" {
  description = "EC2 instance type for the shared host"
  type        = string
  default     = "t3.micro"
}

variable "ami_id" {
  description = "AMI ID currently running on the instance"
  type        = string
  default     = "ami-0fd6240f599091088"
}
