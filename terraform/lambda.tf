resource "aws_lambda_function" "market_twits" {
  function_name = "MarketTwits"

  # This function is deployed as a container image, so handler/runtime are unset.
  package_type = "Image"
  image_uri    = "571944667415.dkr.ecr.eu-north-1.amazonaws.com/daily-news-lambda@sha256:6dc9dcfd7690444cf0efc774159b75686537ef2659baac601da6a80e57af2036"
  publish      = false

  role         = "arn:aws:iam::571944667415:role/service-role/MarketTwits-role-jhjzhrsg"
  memory_size  = 256
  timeout      = 60
  architectures = ["x86_64"]

  lifecycle {
    ignore_changes = [
      # Don't force secrets into git; manage env vars separately (e.g. SSM/Secrets Manager) later.
      environment,
    ]
  }
}

