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
        pypkgs.lxml
        pypkgs.selenium
        pypkgs.requests
        pypkgs.pandas
        pypkgs.fuzzywuzzy
        pypkgs.ipython
        pypkgs.nose
    ];
}
