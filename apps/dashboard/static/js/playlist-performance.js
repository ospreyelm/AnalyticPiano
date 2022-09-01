$("td").each(function () {
  $(this).html(
    $(this)
      .html()
      .replace(
        /(Pass )/gi,
        '<span style="color:green; font-weight: bold">$1</span>'
      )
  );
  $(this).html(
    $(this)
      .html()
      .replace(
        /(Error\x28s\x29)/gi,
        '<span style="color:red; font-weight: bold">$1</span>'
      )
  );
});
