provider "aws" {
  region = var.aws_region
}

resource "aws_instance" "arbitrage_bot" {
  ami           = var.ami_id
  instance_type = var.instance_type

  key_name = var.key_name

  vpc_security_group_ids = [aws_security_group.arbitrage_bot_sg.id]

  user_data = file("${path.module}/scripts/start.sh")

  tags = {
    Name = "ArbitrageBot"
  }
}

resource "aws_security_group" "arbitrage_bot_sg" {
  name_prefix = "arbitrage_bot_sg"

  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 5000
    to_port     = 5000
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

resource "aws_iam_role" "arbitrage_bot_role" {
  name = "arbitrage_bot_role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "arbitrage_bot_policy_attachment" {
  role       = aws_iam_role.arbitrage_bot_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2FullAccess"
}

resource "aws_iam_instance_profile" "arbitrage_bot_profile" {
  name = "arbitrage_bot_profile"
  role = aws_iam_role.arbitrage_bot_role.name
}