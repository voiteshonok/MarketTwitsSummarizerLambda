resource "aws_db_instance" "market_twits" {
  identifier = "database-1"

  instance_class = "db.t4g.micro"
  engine         = "postgres"

  allocated_storage   = 20
  storage_type        = "gp2"
  storage_encrypted   = true
  publicly_accessible = true
  multi_az            = false

  db_name        = "twits"
  username       = "postgres"
  port           = 5432
  backup_retention_period = 1
  deletion_protection     = false

  db_subnet_group_name   = "default-vpc-0a49ba0f74dad669f"
  vpc_security_group_ids = ["sg-06246e6765a49aeb8"]

  lifecycle {
    ignore_changes = [
      # Don't manage password from Terraform without a secrets strategy.
      password,
      # Reduce churn from AWS-managed minor versions / drift.
      engine_version,
    ]
  }
}

