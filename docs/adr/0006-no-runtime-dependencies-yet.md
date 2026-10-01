# The application has no runtime dependencies yet

`src/` ships to Lambda unpackaged, so it may import only the standard library and
`boto3`. How to package a dependency (a bundled asset, a layer or an image; see
[development.md](../development.md#adding-a-runtime-dependency)) depends on what the
first dependency is, and building it early would mean maintaining a guess.
