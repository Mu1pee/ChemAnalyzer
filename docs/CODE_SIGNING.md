# Optional Windows signing

Current builds are intentionally unsigned. No certificate is generated, installed or trusted automatically. SmartScreen and Windows security settings remain unchanged.

The installed electron-builder already supports Windows signing. When a legitimate certificate/service becomes available, keep its credentials outside Git and provide WIN_CSC_LINK and WIN_CSC_KEY_PASSWORD to the build process through a secure local environment or CI secrets. A hardware-backed certificate or cloud signing service requires its provider's supported integration instead of exporting a private key.

For a certificate-backed release, enable build.forceCodeSigning=true so missing signing credentials fail the build. Verify the resulting EXE with Get-AuthenticodeSignature and confirm publisher identity and timestamp before distribution. A successful build alone is not evidence of a trusted signature.

Do not commit certificate files or passwords. Unsigned research builds remain supported through the existing package.json configuration. Signing does not replace testing and does not guarantee SmartScreen reputation.
