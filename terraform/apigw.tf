resource "aws_apigatewayv2_api" "twits_tg_api" {
  name          = "TwitsTgApi"
  protocol_type = "HTTP"
}

