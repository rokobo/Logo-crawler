# Logo crawler

This program accepts domain names on `STDIN` and writes a CSV of domain and logo URL to `STDOUT`. It is made to be used inside of a nix shell and uses multiprocessing for faster processing.

## Running the application

Open the nix shell with `nix-shell`, start the python application with `python main.py`, then you can input URLs separated by a space. For example:

```python
google.com facebook.com instagram.com
```

The program will generate a CSV with these sites and output it to `STDOUT`.
