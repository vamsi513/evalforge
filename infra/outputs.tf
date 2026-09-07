output "instance_id" {
  description = "EC2 instance ID of the shared resume-projects host"
  value       = aws_instance.resume_projects.id
}

output "public_ip" {
  description = "Elastic IP address the host is reachable at"
  value       = aws_eip.resume_projects.public_ip
}

output "security_group_id" {
  description = "Security group ID governing inbound access to the host"
  value       = aws_security_group.resume_projects.id
}
