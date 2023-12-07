{ pkgs ? import <nixpkgs> {} }:

let
    python = pkgs.python311;
    pypkgs = python.pkgs;
in
pkgs.mkShell rec {
    name = "interview";
    shellHook = ''
        source .bashrc
    '';
    buildInputs = with pkgs; [
        chromedriver
        chromium
        pypkgs.python
        pypkgs.selenium
        pypkgs.requests
        pypkgs.pandas
        pypkgs.beautifulsoup4
        pypkgs.fuzzywuzzy
        pypkgs.ipython
        pypkgs.nose
    ];
}
