# to get performer/members details we can call the following endpoint:
`GET /eapi/v1/circle/members`

example response:
```json
[
  {
    "id": 1,
    "userId": 1,
    "circleId": 1,
    "role": "admin",
    "isActive": true,
    "createdAt": "2024-06-30T23:19:39.316453-04:00",
    "updatedAt": "2024-06-30T23:19:39.316453-04:00",
    "points": 0,
    "pointsRedeemed": 0,
    "username": "114661255506921586535",
    "displayName": "Mohamad",
    "image": "https://lh3.googleusercontent.com/a/ACg8ocIGS7z3diKkYG66GdU_oaOVe9ZJVn3sUfQ9v8IdkQsQS3jdA3snxg=s96-c"
  }
]
```