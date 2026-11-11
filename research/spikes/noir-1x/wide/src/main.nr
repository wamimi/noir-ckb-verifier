// R1 survey circuit: integer division, bit operations, array reads and writes at a
// witness index, a comparison, and a return value. Not an application.
fn main(a: u64, b: u64, idx: u32, arr: [Field; 4], x: pub Field) -> pub Field {
    let c = a / b;
    let d = (a ^ b) & 0xff;
    let e = arr[idx];
    let mut arr2 = arr;
    arr2[idx] = x;
    assert(a > b);
    assert(c as Field + d as Field != 0);
    e + arr2[0]
}
