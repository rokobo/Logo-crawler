# Logo crawler

<p align="center">
  <img src="https://github.com/rokobo/Logo-crawler/blob/main/thumbnail.png?raw=true"/>
</p>

This program accepts domain names on `STDIN` and writes a CSV of domain and logo URL to `STDOUT`. It is made to be used inside of a nix shell and uses multithreading for faster processing.

## Running the application

Open the nix shell with `nix-shell`, start the python application with `python main.py`, then you can input URLs separated by a space. For example:

```python
google.com facebook.com instagram.com
```

The program will generate a CSV with these sites and output it to `STDOUT`.

## Configuration

Depending on you internet speed and number of available threads, the page load timeout may be too low. Adjusting the timeout in `driver.set_page_load_timeout(90)` and the number of workers in `ThreadPoolExecutor(max_workers=10)` can help make the program more reliable.

The `process()` function can be modified in its scoring criteria, which can be tailored to your needs.
