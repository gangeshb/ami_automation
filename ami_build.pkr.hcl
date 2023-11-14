# ami_build.pkr.hcl
variable "ami_name" {
  type =  string
  default = ""
}
variable "instance_type" {
  type =  string
  default = "t2.micro"
}
variable "region" {
  type =  string
  default = "ap-south-1"
}
variable "source_ami" {
  type =  string
  default = "ami-06791f9213cbb608b"
}
variable "vpc_id" {
  type =  string
  default = "vpc-012f5b7f773d5240b"
}
variable "subnet_id" {
  type =  string
  default = "subnet-03a681e98da271531"
}
variable "ssh_username" {
  type =  string
  default = "ec2-user"
}
variable "provisioner_script" {
  type =  string
  default = "./script.sh"
}

packer {
  required_plugins {
    amazon = {
      version = ">= 1.2.6"
      source  = "github.com/hashicorp/amazon"
    }
  }
}

source "amazon-ebs" "base" {
  ami_name      = var.ami_name
  instance_type = var.instance_type
  region        = var.region
  source_ami    = var.source_ami
  vpc_id        = var.vpc_id
  subnet_id     = var.subnet_id
  ssh_username  = var.ssh_username

 tags = {
    Name = var.ami_name
  }

}

build {
  sources = ["source.amazon-ebs.base"]

  provisioner "shell" {
    script = var.provisioner_script
    pause_before = "10s"
    timeout      = "20m"
  }
}
